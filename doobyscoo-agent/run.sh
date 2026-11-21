
./.venv/bin/python -m doobyscoo serve \
    --model models/dog.pt \
    --port 8765 \
    --maps maps/played \
    --train-maps maps/train \
    --val-maps maps/validation \
    --learn-updates 5
