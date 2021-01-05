import json
import datetime
import random

from django.db import models
from spoilr.models import *
from asgiref.sync import async_to_sync

from hunt.teamwork import TeamworkTimeConsumer
from .validate import Validator as V
from .gen_grid_list import _get_score_dict
from .gen_grid import gen_grid

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

class BoggleHighScoreData(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    level = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)

# TODO: make sure these are reasonable
TIME_LIMITS_PER_LEVEL = [
    datetime.timedelta(seconds=120),
    datetime.timedelta(seconds=120),
    datetime.timedelta(seconds=120),
    datetime.timedelta(seconds=120),
]

TESTING_BOARDS = [
  [
    ["#", "#", "#", "#", "#", "#"],
    ["#", "c", "d", "e", "f", "#"],
    ["#", "h", "i", "j", "k", "#"],
    ["#", "n", "o", "p", "qu", "#"],
    ["#", "s", "t", "u", "v", "#"],
    ["#", "#", "#", "#", "#", "#"],
  ],
  [
    ["#", "#", "a", "b", "c"],
    ["#", "e", "f", "g", "h"],
    ["i", "j", "k", "l", "m"],
    ["n", "o", "p", "qu", "#"],
    ["r", "s", "t", "#", "#"],
  ],
  [
    ["#", "#", "a", "b", "#", "#"],
    ["#", "c", "d", "e", "f", "#"],
    ["g", "h", "i", "j", "k", "l"],
    ["m", "n", "o", "p", "qu", "r"],
    ["#", "s", "t", "u", "v", "#"],
    ["#", "#", "w", "x", "#", "#"],
  ],
  [
    [
      ["a", "b", "c"],
      ["d", "e", "f"],
      ["g", "h", "i"],
    ],
    [
      ["j", "k", "l"],
      ["m", "n", "o"],
      ["p", "qu", "r"],
    ],
    [
      ["s", "t", "u"],
      ["v", "w", "x"],
      ["y", "z", "a"],
    ],
  ],
]

class BoggleGameSpec:
    def __init__(self, level, grid, bonuses, wordlist, special):
        self.level = level
        self.grid = grid
        self.bonuses = bonuses
        self.wordlist = wordlist
        self.special = special

    @staticmethod
    def get_testing_spec(level):
        board = TESTING_BOARDS[level]
        wordlist = [
            (word, score) for word, score in
            _get_score_dict(board, level, {}, "").items()
        ]
        return BoggleGameSpec(
            level,
            board,
            {},
            wordlist,
            wordlist[0][0]
        )

DATABASE_VERSION = 4
ANSWER = 'NOHTDORUWEAARLDN'
HISCORE_SCALE = 100000

# TODO: make sure this is eventually 100
CACHE_SIZE = 100
game_spec_cache = {}

def gen_game_spec(level, seed):
    grid, bonuses, special = gen_grid(level, seed)
    wordlist = [
        (word, score) for word, score in
        _get_score_dict(grid, level, bonuses, special).items()
    ]
    return BoggleGameSpec(
        level, grid, bonuses, wordlist, special
    )

def discard_game_spec_from_cache(game_data):
    global game_spec_cache

    level = game_data['level']
    seed = game_data['seed']
    key = (level, seed)
    game_spec_cache.pop(key, None)

def get_game_spec(game_data):
    global game_spec_cache

    level = game_data['level']
    seed = game_data['seed']
    key = (level, seed)
    if key in game_spec_cache:
        game_spec_cache[key] = (
            datetime.datetime.now(),
            game_spec_cache[key][1]
        )
    else:
        if len(game_spec_cache) >= CACHE_SIZE:
            game_spec_cache = {
                k: v for k, v in
                sorted([
                    (k, v) for k, v in game_spec_cache.items()
                ], key=lambda k: k[0], reverse=True)[:CACHE_SIZE//2]
            }
        game_spec_cache[key] = (
            datetime.datetime.now(),
            gen_game_spec(level, seed)
        )
    return game_spec_cache[key][1]

def get_total_score(game_spec, words):
    return sum([w[1] for w in words])

def get_max_score(game_spec):
    return sum([w[1] for w in game_spec.wordlist])

# TODO: make sure these are reasonable numbers
TROPHY_NUM_WORDS_THRESHOLD = 0.3
TROPHY_POINTS_THRESHOLD = 0.2
L3_TROPHY_NUM_WORDS_THRESHOLD = 0.15
L3_TROPHY_POINTS_THRESHOLD = 0.05

def gets_trophy_num(game_spec, words):
    threshold = L3_TROPHY_NUM_WORDS_THRESHOLD if (level == 3) else TROPHY_NUM_WORDS_THRESHOLD
    return len(words) >= len(game_spec.wordlist) * threshold

def gets_trophy_points(game_spec, words):
    level = game_spec.level
    score = get_total_score(game_spec, words)
    max_score = get_max_score(game_spec)
    threshold = L3_TROPHY_POINTS_THRESHOLD if (level == 3) else TROPHY_POINTS_THRESHOLD
    return score >= max_score * threshold

def gets_trophy_longest(game_spec, words):
    max_len = max(len(w[0]) for w in words)
    max_len_all = max(len(w[0]) for w in game_spec.wordlist)
    return max_len >= max_len_all

def gets_trophy_special(game_spec, words):
    return len([w for w in words if w[0] == game_spec.special]) > 0

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

def game_get_max_score(game_data):
    return get_max_score(get_game_spec(game_data))

def game_get_score(game_data):
    return get_total_score(get_game_spec(game_data), game_data['words'])

def game_get_max_num_words(game_data):
    return len(get_game_spec(game_data).wordlist)

def game_get_num_words(game_data):
    return len(game_data['words'])

def game_get_special(game_data):
    return get_game_spec(game_data).special

def game_get_found_special(game_data):
    special = game_get_special(game_data)
    return len([w for w in game_data['words'] if w[0] == special]) > 0

class BoggleStats:
    def __init__(self):
        self.tot_words = 0 # total number of words, ever
        self.best_score = [
            None, None, None, None
        ] # best % score for each level
        self.best_num_words = [
            None, None, None, None
        ] # best % words for each level
        self.highest_scoring = [
        ] # highest scoring normal words found
        self.special = [
        ] # special words found

    def from_dict(self, d):
        self.tot_words = d['tot_words']
        self.best_score = d['best_score']
        self.best_num_words = d['best_num_words']
        self.highest_scoring = d['highest_scoring']
        self.special = d['special']

    def to_dict(self):
        return {
            'tot_words': self.tot_words,
            'best_score': self.best_score,
            'best_num_words': self.best_num_words,
            'highest_scoring': self.highest_scoring,
            'special': self.special,
        }

    def update_stats(self, game_data):
        self.tot_words += len(game_data['words'])
        level = game_data['level']
        score = game_get_score(game_data) / game_get_max_score(game_data)
        num_words = game_get_num_words(game_data) / game_get_max_num_words(game_data)
        if self.best_score[level] is None or score > self.best_score[level]:
            self.best_score[level] = score
        if self.best_num_words[level] is None or num_words > self.best_num_words[level]:
            self.best_num_words[level] = num_words

        all_entries = sorted(self.highest_scoring + game_data['words'], key=lambda entry: entry[1], reverse=True)
        scores_dict = {}
        self.highest_scoring = []
        for entry in all_entries:
            if entry[0] not in scores_dict:
                scores_dict[entry[0]] = entry[1]
                self.highest_scoring += [entry]
                if len(self.highest_scoring) >= 3:
                    break

        if game_get_found_special(game_data):
            self.special = list(set(self.special + [game_get_special(game_data)]))

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
            'round_trophies': 0, # bitmask
            'trophies': 0, # bitmask
            'stats': BoggleStats(),
        }

    # WARNING: for simplicity, reducer is allowed to mutate game_data
    @transaction.atomic
    def handle_txn(self, reducer, msg):
        data = BoggleTeamData.objects.get_or_create(team=self.team)[0]

        try:
            game_data = json.loads(data.world)
            stats = BoggleStats()
            stats.from_dict(game_data['stats'])
            game_data['stats'] = stats
        except:
            game_data = self.make_init()

        if game_data['version'] < DATABASE_VERSION:
            game_data = self.make_init()

        new_game_data, actions = reducer(game_data, msg)

        if new_game_data is not None:
            new_game_data['stats'] = new_game_data['stats'].to_dict()
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

    def get_cl_tot_time(self, game_data):
        return self.get_time_limit(game_data) / datetime.timedelta(milliseconds=1)

    def cl_num_games_valid(self, game_data, msg):
        if not V.has_key(msg, 'numGames') or not V.is_nat(msg['numGames']):
            return False
        num_games_c = msg['numGames']
        num_games_s = game_data['num_games']
        if num_games_c < num_games_s:
            return False
        return True

    def stop_game(self, game_data):
        found_special = game_get_found_special(game_data)
        all_words = [
            w for w in get_game_spec(game_data).wordlist
            if found_special or w[0] != get_game_spec(game_data).special
        ]

        game_data['stats'].update_stats(game_data)
        max_score = game_get_max_score(game_data)
        hiscore = int(game_get_score(game_data) / max_score * HISCORE_SCALE)
        self.set_hiscore(game_data['level'], hiscore)
        discard_game_spec_from_cache(game_data)
        game_data['running'] = False
        game_data['start_time'] = None
        game_data['seed'] = None
        game_data['level'] = None
        game_data['words'] = None
        game_data['round_trophies'] = 0

        return self.make_full_update(game_data, True, all_words=all_words)

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

    def make_full_update(self, game_data, broadcast=False, all_words=None):
        is_running = game_data['running']
        max_level = game_data['max_level']
        msg = {
            'type': 'full',
            'numGames': game_data['num_games'],
            'maxLevel': max_level,
            'running': is_running,
            'trophies': self.get_trophy_string(game_data),
            'roundTrophies': game_data['round_trophies'],
            'stats': game_data['stats'].to_dict(),
        }

        if max_level >= 4:
            msg['blanks'] = '_ _ _ _ _ _ _ _ _ _   _ _ _ _ _ _'

        if is_running:
            words = game_data['words']

            msg['level'] = game_data['level']
            msg['timeLeft'] = self.get_cl_time_left(game_data)
            msg['totTime'] = self.get_cl_tot_time(game_data)
            msg['words'] = words
            msg['score'] = game_get_score(game_data)
            msg['grid'] = get_game_spec(game_data).grid
            msg['bonuses'] = [[k, v] for k, v in get_game_spec(game_data).bonuses.items()]
            msg['totNumWords'] = game_get_max_num_words(game_data)
            msg['debugSeed'] = game_data['seed']

            special = game_get_special(game_data)
            found_special = game_get_found_special(game_data)
            if found_special:
                msg['special'] = special

        if all_words is not None:
            msg['allWords'] = all_words

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
        game_data['seed'] = random.SystemRandom().randrange(1<<28)
        game_data['level'] = level
        game_data['words'] = []
        game_data['round_trophies'] = 0
        print(game_data['seed'])
        print(game_get_special(game_data))
        return game_data, self.make_full_update(game_data, True)

    def handle_stop(self, game_data, msg):
        if not game_data['running']:
            return None, self.make_full_update(game_data)
        if not self.cl_num_games_valid(game_data, msg):
            return None, self.make_full_update(game_data)

        found_special = game_get_found_special(game_data)
        all_words = [w for w in get_game_spec(game_data).wordlist if found_special or w[0] != get_game_spec(game_data).special]
        actions = self.stop_game(game_data)
        return game_data, actions

    def get_round_trophies(self, game_data):
        level = game_data['level']
        trophies_per_level = len(GETS_TROPHY_FUNCS)

        trophies = 0
        for i in range(trophies_per_level):
            trophy_index = level * trophies_per_level + i
            if gets_trophy(game_data, i):
                trophies |= 1 << trophy_index
        return trophies

    def handle_word(self, game_data, msg):
        if not V.has_key(msg, 'word') or not V.is_str(msg['word']):
            return None, []
        word = msg['word']

        if not game_data['running']:
            return None, self.make_full_update(game_data)
        if not self.cl_num_games_valid(game_data, msg):
            return None, self.make_full_update(game_data)

        if self.get_time_left(game_data) < datetime.timedelta():
            actions = self.stop_game(game_data)
            return game_data, actions

        game_spec = get_game_spec(game_data)
        entries = [w for w in game_spec.wordlist if w[0] == word]
        if len(entries) == 0:
            return None, self.make_grade(word, GRADE_WRONG)
        entry = entries[0]
        if len([w for w in game_data['words'] if w[0] == entry[0]]) > 0:
            return None, self.make_grade(word, GRADE_DUPLICATE)

        game_data['words'] += [[entry[0], entry[1]]]

        round_trophies = self.get_round_trophies(game_data)
        new_trophies = round_trophies & (~game_data['trophies'])
        game_data['trophies'] |= round_trophies
        game_data['round_trophies'] |= round_trophies

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

    def set_hiscore(self, level, score):
        data = BoggleHighScoreData.objects.get_or_create(team=self.team, level=level)[0]
        if score > data.score:
            data.score = score
            data.save()

    def get_hiscores(self, level):
        if not BoggleHighScoreData.objects.filter(level=level).filter(team=self.team).exists():
            return None
        scores = list(BoggleHighScoreData.objects.filter(level=level).order_by('-score').values_list('team__name', 'score'))
        # TODO: add real high score
        # scores += [('✈️✈️✈️ Galactic Trendsetters ✈️✈️✈️', int(0.9 * HISCORE_SCALE))]
        # scores.sort(key=lambda t: t[1], reverse=True)
        return scores

    def handle_get_hiscores(self, msg):
        if not V.has_key(msg, 'level') or not V.is_nat(msg['level'], 4):
            return []
        hiscores = self.get_hiscores(msg['level'])
        return [BoggleAction.make_respond({
            'type': 'hiscores',
            'hiscores': hiscores,
        })]

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
        if msg_type == 'getHiscores':
            actions += self.handle_get_hiscores(msg)

        for action in actions:
            if action.broadcast:
                print('broadcasting ' + str(action.data))
                self.broadcast(action.data)
            else:
                print('sending ' + str(action.data))
                self.respond(action.data)
