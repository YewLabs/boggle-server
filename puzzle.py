import base64
import json
import time

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

class BoggleConsumer(TeamworkTimeConsumer):
    def setup(self):
        super(BoggleConsumer, self).setup(588)

    @transaction.atomic
    def handle_txn(self, reducer, msg):
        data = BoggleTeamData.objects.get_or_create(team=self.team)[0]

        try:
            game_data = json.loads(data.world)
        except:
            game_data = {
                'version': 0,
                'num_games': 0,
                'running': False,
                'start_time': None,
                'seed': None,
                'level': None,
                'words': None,
            }

        new_game_data, actions = reducer(game_data, msg)

        if new_game_data is not None:
            data.world = json.dumps(new_game_data)
            data.save()

        return actions

    def handle_start(self, game_data, msg):
        actions = []
        actions += [BoggleAction.make_broadcast({
            'type': 'update',
        })]
        return game_data, actions

    def handle_word(self, game_data, msg):
        return game_data, []

    def handle_trophies(self, game_data, msg):
        return None, []

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
            'word': self.handle_word,
            'trophies': self.handle_trophies,
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
