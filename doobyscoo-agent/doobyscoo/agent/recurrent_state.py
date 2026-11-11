import torch

REL_DELTAS = ((0, -1), (0, 1), (-1, 0), (1, 0))


class RecurrentState:
    def __init__(self, hiddenSize=128, batchSize=1, device="cpu", h=None, c=None):
        self.hiddenSize = int(hiddenSize)
        self.batchSize = int(batchSize)
        self.device = device
        self.h = torch.zeros(self.batchSize, self.hiddenSize, device=device) if h is None else h
        self.c = torch.zeros(self.batchSize, self.hiddenSize, device=device) if c is None else c
        self.stepCount = 0
        self.lastAction = None
        self.segmentId = 0
        self.pitEntryCount = 0
        self.relPos = (0, 0)
        self.visitCounts = {(0, 0, 0): 1}
        self.edgeCounts = {}
        self.recentActions = []

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
        self.segmentId = 0
        self.pitEntryCount = 0
        self.relPos = (0, 0)
        self.visitCounts = {(0, 0, 0): 1}
        self.edgeCounts = {}
        self.recentActions = []
        return self

    def _copyMetadataTo(self, target):
        target.stepCount = self.stepCount
        target.lastAction = self.lastAction
        target.segmentId = self.segmentId
        target.pitEntryCount = self.pitEntryCount
        target.relPos = self.relPos
        target.visitCounts = dict(self.visitCounts)
        target.edgeCounts = dict(self.edgeCounts)
        target.recentActions = list(self.recentActions)
        return target

    def detach(self):
        cloned = RecurrentState(
            hiddenSize=self.hiddenSize,
            batchSize=self.batchSize,
            device=self.device,
            h=self.h.detach(),
            c=self.c.detach(),
        )
        return self._copyMetadataTo(cloned)

    def clone(self):
        cloned = RecurrentState(
            hiddenSize=self.hiddenSize,
            batchSize=self.batchSize,
            device=self.device,
            h=self.h.clone(),
            c=self.c.clone(),
        )
        return self._copyMetadataTo(cloned)

    def to(self, device):
        self.device = device
        self.h = self.h.to(device)
        self.c = self.c.to(device)
        return self

    def asTuple(self):
        return (self.h, self.c)

    def currentKey(self):
        return (self.segmentId, self.relPos[0], self.relPos[1])

    def neighborKey(self, action):
        dx, dy = REL_DELTAS[int(action)]
        return (self.segmentId, self.relPos[0] + dx, self.relPos[1] + dy)

    def neighborVisitFeatures(self):
        feats = []
        cur = self.currentKey()
        for a in range(4):
            nKey = self.neighborKey(a)
            visits = self.visitCounts.get(nKey, 0)
            edges = self.edgeCounts.get((cur, a), 0)
            feats.append(min(1.0, float(visits + edges) / 4.0))
        return feats

    def directionalMemoryMatrix(self, oppositeActions=(1, 0, 3, 2)):
        rows = []
        cur = self.currentKey()
        pitFirst = 1.0 if self.pitEntryCount == 0 else 0.0
        pitRepeat = 1.0 if self.pitEntryCount > 0 else 0.0
        for a in range(4):
            nKey = self.neighborKey(a)
            visits = min(6.0, float(self.visitCounts.get(nKey, 0))) / 3.0
            edges = min(6.0, float(self.edgeCounts.get((cur, a), 0))) / 3.0
            isRev = 1.0 if (self.lastAction is not None and oppositeActions[self.lastAction] == a) else 0.0
            rows.append([pitFirst, pitRepeat, visits, edges, isRev])
        return rows

    def recordAction(self, observationTensor, action):
        act = int(action)
        cur = self.currentKey()
        self.edgeCounts[(cur, act)] = self.edgeCounts.get((cur, act), 0) + 1

        flat = observationTensor.detach().cpu().view(-1).tolist()
        if len(flat) >= 4:
            maxDir = max(abs(x) for x in flat[:4])
            dirVal = flat[act] * 4.0 if maxDir <= 1.05 else flat[act]
            if dirVal > 0.1:
                if abs(dirVal - 4.0) < 0.25:
                    self.pitEntryCount += 1
                    self.segmentId = 1
                    self.relPos = (0, 0)
                else:
                    dx, dy = REL_DELTAS[act]
                    self.relPos = (self.relPos[0] + dx, self.relPos[1] + dy)

        newKey = self.currentKey()
        self.visitCounts[newKey] = self.visitCounts.get(newKey, 0) + 1
        self.lastAction = act
        self.recentActions.append(act)
        if len(self.recentActions) > 16:
            self.recentActions.pop(0)
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
