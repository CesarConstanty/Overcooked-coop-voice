import numpy as np
from typing import List, Tuple

SIZE = 8

class Grid:
    def __init__(self, arr: np.ndarray = None):
        if arr is None:
            self.arr = np.full((SIZE, SIZE), ' ', dtype='<U1')
        else:
            assert arr.shape == (SIZE, SIZE)
            self.arr = arr.copy()

    @classmethod
    def from_lines(cls, lines: List[str]):
        assert len(lines) == SIZE
        mat = np.array([list(line.rstrip('\n')) for line in lines], dtype='<U1')
        return cls(mat)

    def to_lines(self) -> List[str]:
        return [''.join(self.arr[i, :]) for i in range(SIZE)]

    def save_layout(self, path: str):
        with open(path, 'w') as f:
            for line in self.to_lines():
                f.write(line + '\n')

    @classmethod
    def load_layout(cls, path: str):
        with open(path, 'r') as f:
            lines = [line.rstrip('\n') for line in f.readlines()]
        return cls.from_lines(lines)

    def copy(self):
        return Grid(self.arr)

    # D8 transforms: 4 rotations * 2 (mirror)
    def transforms(self) -> List['Grid']:
        outs = []
        a = self.arr
        for k in range(4):
            r = np.rot90(a, k)
            outs.append(Grid(r))
            outs.append(Grid(np.fliplr(r)))
        return outs

    def canonical_hash(self) -> str:
        forms = self.transforms()
        reps = [''.join(f.to_lines()) for f in forms]
        return min(reps)

    def __str__(self):
        return '\n'.join(self.to_lines())
