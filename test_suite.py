from gen_grid_list import _get_score_dict
from gen_grid import gen_grid
import random, time

words = {}
words_level = {}
t = time.time()
for i in range(500):
    seed = random.randint(0,100000000000)
    for level in range(4):

        grid, bonuses, special = gen_grid(level, seed)

        d = _get_score_dict(grid, level, bonuses, special)
        
        if special not in words:
            words[special] = [len(d)]
        else:
            words[special].append(len(d))
        
    if i % 100 == 99:
        print(time.time()-t)
        print(words)