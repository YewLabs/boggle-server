import sqlite3

with open('site-hiscores.txt', 'r') as f:
    lines = [l.strip() for l in f.read().split('\n') if l.strip() != '']

def get_data(l):
    chunks = l[:-1].rsplit(': ', 1)
    ochunks = chunks[0].rsplit(' (', 1)
    return ochunks[0], int(ochunks[1]), int(chunks[1])
lines = [get_data(l) for l in lines if l != '']

db = sqlite3.connect('../db/db.sqlite')
for l in lines:
    db.execute(' '.join([
		'INSERT OR REPLACE INTO boggle_high_scores',
		'(team, level, score)',
		'VALUES (?, ?, ?)',
    ]), (l[0], l[1], l[2]))
db.commit()
