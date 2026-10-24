# sch5n

Experimental software

## Run

### Python 3.15

#### Linux

    python3.15 -m venv .venv
    source .venv/bin/activate
    pytohn -m pip install uv
    uv pip install -e .

#### Windows

https://www.python.org/downloads/release/pymanager-264/

    py -m venv .venv
    (Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; .\.venv\Scripts\Activate.ps1
    pytohn -m pip install uv
    python -m pip install -e .

## Dependencies

- [Python](https://www.python.org/)
    - [PyGame-CE](https://www.pyga.me)

## Development

### For fast development - No documentation checking

    python -m ruff check . --fix --ignore PLR0915 --ignore PLR0912 --ignore C901 --ignore D417 --ignore D103 --ignore D107 --ignore D101 --ignore D102 --ignore DOC201 --ignore D105 --ignore PLR0911 --ignore DOC501 --ignore PLR0913 --ignore PLR0917 --ignore PLR1702

## Sources

- [Tilemap & particles](https://www.youtube.com/watch?v=2gABYM5M0ww)

- [Map generation](https://www.youtube.com/watch?v=Pgt82G4Jxac)

- [Logging](https://www.youtube.com/watch?v=9L77QExPmI0)