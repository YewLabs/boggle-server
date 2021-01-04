import random, copy

_CARROLLWORDS = ["mimsy", "vorpal", "chortle", "frumious", "slithy", "burble", "borogove", "brillig", "gimble", "jubjub", "manxome", "outgrabe", "tulgey", "uffish", "callay", "callooh", "tumtum", "wabe", "tove"]
_CARROLLWORDS += ["galumph", "frabjous", "snark", "portmanteau"]

def gen_grid(level, seed):
    r = random.Random(seed*4+level)
    _FREQ = [119,29,64,53,181,19,43,37,142,3,13,84,45,108,104,46,3,112,150,105,51,15,12,5,26,8]
    _BONUSES = [{(1,1):2,(4,4):3}, {(0,2):2,(2,4):2,(4,0):2}, {(0,2):2,(5,3):2,(2,5):3,(3,0):3}, {(0,0,0):2,(0,2,2):3,(2,2,0):3,(2,0,2):2}]
    bonuses = _BONUSES[level]

    _PATHS = ((7,8,15,10,9,16,22,28,27,26,21,14,19,25,20,13), (2,7,12,8,3,4,9,14,18,13,17,22,21,20,16,15,10,11,6), (2,10,23,27,16,3,14,25,12,8,21,32,19,15,7,18,26,22,33,20,28,17,9,13), (0,1,2,11,14,23,26,17,16,25,22,19,18,21,24,15,6,7,8,5,4,13,10,9,12,3))
    _PATHCELLS = (16, 19, 24, 26)

    _GRIDS = [0,0,0,0]

    _GRIDS[0] = [["#", "#", "#", "#", "#", "#"],["#", "@", "@", "@", "@", "#"],["#", "@", "@", "@", "@", "#"],["#", "@", "@", "@", "@", "#"],["#", "@", "@", "@", "@", "#"],["#", "#", "#", "#", "#", "#"]]
    _GRIDS[1] = [["#", "#", "@", "@", "@"], ["#", "@", "@", "@", "@"], ["@", "@", "@", "@", "@"], ["@", "@", "@", "@", "#"], ["@", "@", "@", "#", "#"]]
    _GRIDS[2] = [["#", "#", "@", "@", "#", "#"],["#", "@", "@", "@", "@", "#"],["@", "@", "@", "@", "@", "@"],["@", "@", "@", "@", "@", "@"],["#", "@", "@", "@", "@", "#"],["#", "#", "@", "@", "#", "#"]]
    _GRIDS[3] = [[["@", "@", "@"],["@", "@", "@"],["@", "@", "@"]],[["@", "@", "@"],["@", "@", "@"],["@", "@", "@"]],[["@", "@", "@"],["@", "@", "@"],["@", "@", "@"]]]

    grid = _GRIDS[level]

    # generate carroll word:
    cword = r.choice(_CARROLLWORDS)
    indstart = r.randint(0,_PATHCELLS[level]-1)

    for i in range(len(cword)):
        pos = _PATHS[level][(indstart+i) % _PATHCELLS[level]]
        if level == 0 or level == 2:
            x = pos%6
            y = pos//6
            grid[x][y] = cword[i]
        if level == 1:
            x = pos%5
            y = pos//5
            grid[x][y] = cword[i]
        if level == 3:
            x = pos%3
            y = pos//3%3
            z = pos//9
            grid[x][y][z] = cword[i]

    # randomize other letters:

    def generate_letter(level):
        l = chr(ord('a')+r.choices(range(26),weights=_FREQ)[0])
        if l == "q":
            l = "qu"
        return l
    
    if level == 0 or level == 2:
        for x in range(6):
            for y in range(6):
                if grid[x][y] == "@":
                    grid[x][y] = generate_letter(level)
    if level == 1:
        for x in range(5):
            for y in range(5):
                if grid[x][y] == "@":
                    grid[x][y] = generate_letter(level)
    if level == 3:
        for x in range(3):
            for y in range(3):
                for z in range(3):
                    if grid[x][y][z] == "@":
                        grid[x][y][z] = generate_letter(level)
    
    return grid, bonuses, cword
