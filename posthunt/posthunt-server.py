#!/usr/bin/env python3

import json
import sys
import random
import threading
import os
import os.path
import asyncio
import websockets
import http.server
import socketserver
import importlib
import types
import datetime
import sqlite3
import ssl
import pathlib
import urllib.parse

# import logging
# logger = logging.getLogger('websockets')
# logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler())

os.chdir(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, '.')

from game.game import *

WEBSOCKETS_PORT = 29782

all_data = {}
ws_map = {}
ws_queues = {}
team_map = {}
team_last_ping = {}

def game_data_to_dict(game_data):
    game_data['stats'] = game_data['stats'].to_dict()
    return game_data

def load_team_data(team):
    c = db.cursor()
    c.execute(' '.join([
        'SELECT world FROM boggle_team_data',
        'WHERE team = ?'
    ]), (team,))
    entry = c.fetchone()
    if entry is not None:
        all_data[team] = json.dumps(
            game_data_to_dict(from_durable(json.loads(entry[0])))
        )

def load_all_data():
    c = db.cursor()
    c.execute(' '.join([
        'SELECT team, world FROM boggle_team_data',
    ]))
    for entry in c.fetchall():
        all_data[entry[0]] = json.dumps(
            game_data_to_dict(from_durable(json.loads(entry[1])))
        )

load_all_data()

send_queue = []

class BoggleConsumer():
    def __init__(self, channel_name):
        self.channel_name = channel_name

    def handle_txn(self, msg, clid=None):
        global all_data, team_map

        if clid is None:
            clid = self.channel_name

        if not isinstance(msg, dict):
            return []
        if 'type' in msg and msg['type'] == 'AUTH':
            if 'data' in msg:
                team_map[clid] = msg['data'][:256]
            return []
        if clid not in team_map:
            return []
        team = team_map[clid]
        team_last_ping[team] = datetime.datetime.now()

        game = BoggleGameState(team)

        game_data_valid = False
        if team not in all_data:
            load_team_data(team)
        if team in all_data:
            try:
                game_data = json.loads(all_data[team])
                stats = BoggleStats()
                stats.from_dict(game_data['stats'])
                game_data['stats'] = stats
                game_data_valid = True
            except Exception as e:
                game_data = {}

        if not game_data_valid:
            game_data = game.make_init()

        actions = game.handle(game_data, msg)

        if game.new_game_data is not None:
            game_data = game.new_game_data
            game_data['stats'] = game_data['stats'].to_dict()
            all_data[team] = json.dumps(game_data)

        return actions

    def perform_send(self, msg, clid):
        ws_queues[clid].put_nowait(json.dumps(msg))
        if ws_queues[clid].qsize() > 200:
            asyncio.create_task(ws_map[clid].close())

    def perform_actions(self, actions, clid):
        for action in actions:
            if clid not in team_map:
                continue
            team = team_map[clid]
            if not action.broadcast:
                self.perform_send(action.data, clid)
            else:
                targets = [
                    ocl for ocl, oteam in team_map.items()
                    if oteam == team
                ]
                for ocl in targets:
                    self.perform_send(action.data, ocl)

    def process_send_queue(self):
        global send_queue
        while len(send_queue) > 0:
            msg_data = send_queue[0]
            send_queue = send_queue[1:]
            if msg_data[2] == 'disconnect':
                # print(msg_data[1] + ' disconnected')
                # self.handle_disconnect(msg_data[1])
                actions = []
            else:
                # print('received ' + str(msg_data[2]) + ' from ' + msg_data[1])
                actions = self.handle_txn(msg_data[2], msg_data[1])
            self.perform_actions(actions, msg_data[1])

    def disconnected(self):
        global send_queue
        send_queue += [(
            datetime.datetime.now(),
            self.channel_name,
            'disconnect'
        )]
        self.process_send_queue()

    def handle(self, msg):
        global send_queue
        try:
            msg_data = json.loads(msg)
        except JSONDecodeError:
            return;
        send_queue += [(
            datetime.datetime.now(),
            self.channel_name,
            msg_data
        )]
        self.process_send_queue()

old_active_games_str = ''

def log_num_active_games():
    global old_active_games_str
    new_active_games_str = str([
        urllib.parse.quote(team) for team in all_data.keys()
    ])
    if new_active_games_str != old_active_games_str:
        old_active_games_str = new_active_games_str
        print('active games: %s' % (new_active_games_str))

async def send_from_queue(q, ws):
    while True:
        try:
            msg = await q.get()
            if msg is None:
                break
            await ws.send(msg)
        except websockets.exceptions.ConnectionClosedError:
            break
        except websockets.exceptions.ConnectionClosedOK:
            break

connections_cnt = 0

def purge_idle_teams():
    team_not_idle = set()
    for team in team_map.values():
        team_not_idle.add(team)
    all_teams = list(all_data.keys())
    old_num_teams = len(all_data)
    for team in all_teams:
        if team in team_not_idle:
            continue
        if team not in team_last_ping:
            if team in all_data:
                del all_data[team]
            continue
        PING_TIMEOUT = datetime.timedelta(minutes=5)
        if datetime.datetime.now() - team_last_ping[team] < PING_TIMEOUT:
            continue
        del all_data[team]
        del team_last_ping[team]
    log_num_active_games()

async def purge_idle_teams_loop():
    while True:
        await asyncio.sleep(5 * 60)
        purge_idle_teams()

def make_websockets():
    async def on_connect(ws, path):
        global connections_cnt
        name = str(connections_cnt)
        connections_cnt += 1
        ws_map[name] = ws
        ws_queues[name] = asyncio.Queue()
        asyncio.create_task(send_from_queue(ws_queues[name], ws))
        try:
            async for m in ws:
                # print(m)
                BoggleConsumer(name).handle(m)
                log_num_active_games()
        except websockets.exceptions.ConnectionClosedError:
            pass
        finally:
            BoggleConsumer(name).disconnected()
            if name in ws_map:
                del ws_map[name]
            if name in team_map:
                del team_map[name]
            if name in ws_queues:
                ws_queues[name].put_nowait(None)
                del ws_queues[name]
            log_num_active_games()

    start_server = websockets.serve(on_connect, 'localhost', WEBSOCKETS_PORT)
    asyncio.get_event_loop().run_until_complete(start_server)

make_websockets()
asyncio.get_event_loop().create_task(purge_idle_teams_loop())
print('server started')
asyncio.get_event_loop().run_forever()
