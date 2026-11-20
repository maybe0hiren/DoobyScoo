import torch


class RecurrentState:
    """LSTM memory (h, c) for one or more independent episodes.

    A new RecurrentState (all zeros) must be created at every episode boundary;
    it is carried unchanged between steps of the same episode.
    """

    def __init__(self, hiddenSize=128, batchSize=1, device="cpu", h=None, c=None):
        self.hiddenSize = int(hiddenSize)
        self.batchSize = int(batchSize)
        self.device = device
        self.h = torch.zeros(self.batchSize, self.hiddenSize, device=device) if h is None else h
        self.c = torch.zeros(self.batchSize, self.hiddenSize, device=device) if c is None else c
        self.stepCount = 0
        self.lastAction = None

    @classmethod
    def fromTuple(cls, stateTuple):
        if isinstance(stateTuple, cls):
            return stateTuple
        h, c = stateTuple
        return cls(hiddenSize=h.shape[-1], batchSize=h.shape[0], device=h.device, h=h, c=c)

    def reset(self):
        self.h = torch.zeros(self.batchSize, self.hiddenSize, device=self.device)
        self.c = torch.zeros(self.batchSize, self.hiddenSize, device=self.device)
        self.stepCount = 0
        self.lastAction = None
        return self

    def _withTensors(self, h, c):
        out = RecurrentState(hiddenSize=self.hiddenSize, batchSize=self.batchSize, device=self.device, h=h, c=c)
        out.stepCount = self.stepCount
        out.lastAction = self.lastAction
        return out

    def detach(self):
        return self._withTensors(self.h.detach(), self.c.detach())

    def clone(self):
        return self._withTensors(self.h.clone(), self.c.clone())

    def to(self, device):
        self.device = device
        self.h = self.h.to(device)
        self.c = self.c.to(device)
        return self

    def asTuple(self):
        return (self.h, self.c)

    def recordAction(self, observationTensor=None, action=None):
        self.lastAction = None if action is None else int(action)
        self.stepCount += 1

    def __iter__(self):
        yield self.h
        yield self.c

    def __len__(self):
        return 2

    def __getitem__(self, index):
        if index == 0:
            return self.h
        if index == 1:
            return self.c
        raise IndexError("RecurrentState index out of range")
