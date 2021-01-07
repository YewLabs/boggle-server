import pathlib, re
from .gen_grid import _CARROLLWORDS

dataDir = pathlib.Path(__file__).parent.resolve() / 'data'
# feel free to experiment with this
dictDir = dataDir/"dict/enable2k.txt"
fontDir = dataDir/"fonts/Roboto-Medium.ttf"

all_words_l = [word for word in open(str(dictDir))]
all_words_l += _CARROLLWORDS
words = set(word.lower().rstrip('\n') for word in all_words_l if len(word) >= 4) # 4 because all words have trailing \n
prefixes = set(word[:i] for word in words
                for i in range(2, len(word)+1))

def _solve_init(board, level):
    # print(board, level)
    # Return generator of words found

    def solve():
        if level != 3:
            for y, row in enumerate(board):
                for x, letter in enumerate(row):
                    for result in extending(letter, ((x, y),)):
                        yield result
        
        else:
            for z, plane in enumerate(board):
                for y, row in enumerate(plane):
                    for x, letter in enumerate(row):
                        for result in extending3(letter, ((x, y, z),)):
                            yield result

    def extending(prefix, path):
        if prefix in words:
            yield (prefix, path)
        for (nx, ny) in neighbors(path[-1][0], path[-1][1]):
            if (nx, ny) not in path:
                prefix1 = prefix + board[ny][nx]
                if prefix1 in prefixes:
                    for result in extending(prefix1, path + ((nx, ny),)):
                        yield result
    
    def extending3(prefix, path):
        if prefix in words:
            yield (prefix, path)
        for (nx, ny, nz) in neighbors(path[-1][0], path[-1][1], path[-1][2]):
            if (nx, ny, nz) not in path:
                prefix1 = prefix + board[nz][ny][nx]
                if prefix1 in prefixes:
                    for result in extending3(prefix1, path + ((nx, ny, nz),)):
                        yield result

    def neighbors(x, y, z=0):
        if level == 0: #standard adjacency
            for nx in range(max(0, x-1), min(x+2, 6)):
                for ny in range(max(0, y-1), min(y+2, 6)):
                    yield (nx, ny)
        elif level == 1: #hex adjacency
            for nx in range(max(0, x-1), min(x+2, 5)):
                for ny in range(max(0, y-1), min(y+2, 5)):
                    if (nx-x) != (ny-y):
                        yield (nx, ny)
        elif level == 2: #knight adjacency
            d = ((1,2),(2,1),(-1,2),(-2,1),(-1,-2),(-2,-1),(1,-2),(2,-1))
            for dd in d:
                if 0 <= dd[0] + x <= 5 and 0 <= dd[1] + y <= 5:
                    yield (dd[0]+x,dd[1]+y)
        elif level == 3: #3d adjacency
            d = ((0,0,1),(0,1,0),(1,0,0),(0,0,-1),(0,-1,0),(-1,0,0))
            for dd in d:
                if 0 <= dd[0]+x <= 2 and 0 <= dd[1]+y <= 2 and 0 <= dd[2]+z <= 2:
                    yield (dd[0]+x,dd[1]+y,dd[2]+z)
    
    return solve()

def _get_score_dict(board, level, bonus, cword=""):
    valid_words = {}
    def score_word(x):
        #if x == cword:
        #    return 250
        x = len(x)
        if x <= 6:
            return (x-2)*(x-3)*5+10
        else:
            return x*40-170

    for i in _solve_init(board, level):
        score = score_word(i[0])
        for c in i[1]:
            if c in bonus:
                score *= bonus[c]
        if i[0] in valid_words:
            if score > valid_words[i[0]]:
                valid_words[i[0]] = score
        else:
            valid_words[i[0]] = score
    
    return valid_words

def test():
    level = 0
    board = [["#", "#", "a", "b", "#", "#"],["#", "c", "d", "e", "f", "#"],["g", "h", "i", "j", "k", "l"],["m", "n", "r", "p", "qu", "r"],["#", "s", "t", "u", "v", "#"],["#", "#", "w", "x", "#", "#"]]
    bonus = {(1,1):3,(4,4):2}

    _get_score_dict(board, level, bonus)
