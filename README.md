# sch5n

Experimental software

## Run

### Linux

    python -m venv venv
    source venv/bin/activate
    python -m pip install -e .

### Windows

    python -m venv venv
    (Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; .\venv\Scripts\Activate.ps1
    python -m pip install -e .

## Dependencies

- [Python](https://www.python.org/)
    - [Pygame](https://www.pygame.org/news)

## Development

### For fast development

    python -m ruff check . --fix --ignore PLR0915 --ignore PLR0912 --ignore C901 --ignore D417 --ignore D103 --ignore D107 --ignore D101 --ignore D102 --ignore DOC201 --ignore D105 --ignore PLR0911 --ignore DOC501 --ignore PLR0913 --ignore PLR0917 --ignore PLR1702

## Sources

- [Tilemap & particles](https://www.youtube.com/watch?v=2gABYM5M0ww&t=8555s&ab_channel=DaFluffyPotato)

- [Map generation](https://www.youtube.com/watch?v=Pgt82G4Jxac&ab_channel=griffpatch)
