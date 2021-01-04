import json
import datetime
import random

from django.db import models
from spoilr.models import *
from asgiref.sync import async_to_sync

from hunt.teamwork import TeamworkTimeConsumer
from .validate import Validator as V
# from .boggle_backend import gen_image

class BoggleAction:
    def __init__(self, broadcast, data):
        self.broadcast = broadcast
        self.data = data

    @staticmethod
    def make_respond(data):
        return BoggleAction(False, data)

    @staticmethod
    def make_broadcast(data):
        return BoggleAction(True, data)

class BoggleTeamData(models.Model):
    team = models.OneToOneField(Team, on_delete=models.CASCADE)
    world = models.TextField()

TIME_LIMITS_PER_LEVEL = [
    datetime.timedelta(seconds=1),
    datetime.timedelta(seconds=1),
    datetime.timedelta(seconds=1),
    datetime.timedelta(seconds=1),
]

class BoggleGameSpec:
    def __init__(self, level, grid, wordlist, special):
        self.level = level
        self.grid = grid
        self.wordlist = wordlist
        self.special = special

    @staticmethod
    def get_testing_spec(level):
        testing_words = [
            'red',
            'orange',
            'yellow',
            'green',
            'blue',
            'indigo',
            'violet'
        ]
        return BoggleGameSpec(
            level,
            'abcdefghijkl',
            [(word, len(word)) for word in testing_words],
            'green'
        )

DATABASE_VERSION = 1
ANSWER = 'THISISANANSWER!!'

def get_game_spec(game_data):
    level = game_data['level']
    seed = game_data['seed']
    # TODO: cache
    return BoggleGameSpec.get_testing_spec(level)

def get_total_score(game_spec, words):
    return sum([
        next(w[1] for w in game_spec.wordlist if w[0] == word)
        for word in words
    ])

def gets_trophy_num(game_spec, words):
    return len(words) * 2 >= len(game_spec.wordlist)

def gets_trophy_points(game_spec, words):
    score = get_total_score(game_spec, words)
    max_score = sum([w[1] for w in game_spec.wordlist])
    return score * 2 >= max_score

def gets_trophy_longest(game_spec, words):
    max_len = max(len(word) for word in words)
    max_len_all = max(len(w[0]) for w in game_spec.wordlist)
    return max_len >= max_len_all

def gets_trophy_special(game_spec, words):
    return game_spec.special in words

GETS_TROPHY_FUNCS = [
    gets_trophy_num,
    gets_trophy_points,
    gets_trophy_longest,
    gets_trophy_special,
]

def gets_trophy(game_data, index):
    game_spec = get_game_spec(game_data)
    words = game_data['words']
    return GETS_TROPHY_FUNCS[index](game_spec, words)

# response codes to client words
GRADE_WRONG = 0
GRADE_DUPLICATE = 1
GRADE_CORRECT = 2

class BoggleConsumer(TeamworkTimeConsumer):
    def setup(self):
        super(BoggleConsumer, self).setup(588)

    def make_init(self):
        # we must make a new copy of this each time
        # since reducers mutate
        return {
            'version': DATABASE_VERSION,
            'max_level': 0,
            # num_games is used to synchronize client game version
            # so that inputs from stale games get discarded correctly
            'num_games': 0,
            'running': False,
            'start_time': None,
            'seed': None,
            'level': None,
            'words': None,
            'trophies': 0, # bitmask
        }

    # WARNING: for simplicity, reducer is allowed to mutate game_data
    @transaction.atomic
    def handle_txn(self, reducer, msg):
        data = BoggleTeamData.objects.get_or_create(team=self.team)[0]

        try:
            game_data = json.loads(data.world)
        except:
            game_data = self.make_init()

        if game_data['version'] < DATABASE_VERSION:
            game_data = self.make_init()

        new_game_data, actions = reducer(game_data, msg)

        if new_game_data is not None:
            data.world = json.dumps(new_game_data)
            data.save()

        return actions

    def get_time_limit(self, game_data):
        if not game_data['running']:
            return None
        return TIME_LIMITS_PER_LEVEL[game_data['level']]

    def get_time_left(self, game_data):
        if not game_data['running']:
            return None
        start_time = datetime.datetime.fromtimestamp(game_data['start_time'])
        elapsed = datetime.datetime.now() - start_time
        time_left = self.get_time_limit(game_data) - elapsed
        return time_left

    def get_cl_time_left(self, game_data):
        time_left = self.get_time_left(game_data)
        if time_left is None:
            return None
        if time_left < datetime.timedelta():
            time_left = datetime.timedelta()
        return time_left / datetime.timedelta(milliseconds=1)

    def get_score(self, game_data):
        return get_total_score(get_game_spec(game_data), game_data['words'])

    def cl_num_games_valid(self, game_data, msg):
        if not V.has_key(msg, 'numGames') or not V.is_nat(msg['numGames']):
            return False
        num_games_c = msg['numGames']
        num_games_s = game_data['num_games']
        if num_games_c < num_games_s:
            return False
        return True

    def stop_game(self, game_data):
        game_data['running'] = False
        game_data['start_time'] = None
        game_data['seed'] = None
        game_data['level'] = None
        game_data['words'] = None

    def get_trophy_string(self, game_data):
        res = ''
        for i in range(len(ANSWER)):
            has_trophy = ((game_data['trophies'] >> i) & 1) == 1
            res += ANSWER[i] if has_trophy else '?'
        return res

    # grades are
    # - 0: wrong
    # - 1: duplicate
    # - 2: correct
    def make_grade(self, word, grade):
        return [BoggleAction.make_respond({
            'type': 'grade',
            'word': word,
            'grade': grade,
        })]

    def make_full_update(self, game_data, broadcast=False):
        is_running = game_data['running']
        msg = {
            'type': 'full',
            'numGames': game_data['num_games'],
            'maxLevel': game_data['max_level'],
            'running': is_running,
            'trophies': self.get_trophy_string(game_data),
        }

        if is_running:
            msg['level'] = game_data['level']
            msg['timeLeft'] = self.get_cl_time_left(game_data)
            msg['words'] = game_data['words']
            msg['score'] = self.get_score(game_data)
            msg['grid'] = get_game_spec(game_data).grid

        return [BoggleAction(broadcast, msg)]

    def handle_start(self, game_data, msg):
        if not V.has_key(msg, 'level') or not V.is_nat(msg['level'], 4):
            return None, []
        level = msg['level']

        if game_data['running']:
            return None, self.make_full_update(game_data)
        if level > game_data['max_level']:
            return None, self.make_full_update(game_data)

        game_data['num_games'] += 1
        game_data['running'] = True
        game_data['start_time'] = datetime.datetime.timestamp(datetime.datetime.now())
        game_data['seed'] = random.randrange(1<<30)
        game_data['level'] = level
        game_data['words'] = []
        return game_data, self.make_full_update(game_data, True)

    def handle_stop(self, game_data, msg):
        if not game_data['running']:
            return None, self.make_full_update(game_data)
        if not self.cl_num_games_valid(game_data, msg):
            return None, self.make_full_update(game_data)

        self.stop_game(game_data)
        return game_data, self.make_full_update(game_data, True)

    def get_new_trophies(self, game_data):
        level = game_data['level']
        trophies_per_level = len(GETS_TROPHY_FUNCS)

        new_trophies = 0
        for i in range(trophies_per_level):
            trophy_index = level * trophies_per_level + i
            if ((game_data['trophies'] >> trophy_index) & 1) == 1:
                continue
            if gets_trophy(game_data, i):
                new_trophies |= 1 << trophy_index
        return new_trophies

    def handle_word(self, game_data, msg):
        if not V.has_key(msg, 'word') or not V.is_str(msg['word']):
            return None, []
        word = msg['word']

        if not game_data['running']:
            return None, self.make_full_update(game_data)
        if not self.cl_num_games_valid(game_data, msg):
            return None, self.make_full_update(game_data)

        if self.get_time_left(game_data) < datetime.timedelta():
            self.stop_game(game_data)
            return game_data, self.make_full_update(game_data)

        # TODO: check if word is in wordlist
        game_spec = get_game_spec(game_data)
        if word not in [w[0] for w in game_spec.wordlist]:
            return None, self.make_grade(word, GRADE_WRONG)
        if word in game_data['words']:
            return None, self.make_grade(word, GRADE_DUPLICATE)

        game_data['words'] += [word]

        new_trophies = self.get_new_trophies(game_data)
        game_data['trophies'] |= new_trophies

        # unlock if solvers get any trophy in level
        if new_trophies != 0:
            game_data['max_level'] = min(
                max(
                    game_data['max_level'],
                    game_data['level'] + 1
                ),
                4
            )

        # TODO: only need to send things that changed
        return game_data, self.make_grade(word, GRADE_CORRECT) + self.make_full_update(game_data, True)

    # used to get full updates, e.g. on join
    def handle_get_update(self, game_data, msg):
        return game_data, self.make_full_update(game_data)

    def handle(self, msg):
        print('received ' + str(msg) + ' from ' + self.channel_name)

        # this should be all the validation that is performed
        # before update_pings is called
        if not V.is_dict(msg) or not V.has_key(msg, 'type'):
            return
        msg_type = msg['type']
        # for debug server
        if msg_type == 'AUTH':
            return

        reducers = {
            'start': self.handle_start,
            'stop': self.handle_stop,
            'word': self.handle_word,
            'getUpdate': self.handle_get_update,
        }

        actions = []
        if msg_type in reducers:
            actions += self.handle_txn(reducers[msg_type], msg)

        for action in actions:
            if action.broadcast:
                print('broadcasting ' + str(action.data))
                self.broadcast(action.data)
            else:
                print('sending ' + str(action.data))
                self.respond(action.data)
