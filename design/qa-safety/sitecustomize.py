try:
    import dotenv
except ImportError:
    pass
else:
    dotenv.load_dotenv = lambda *args, **kwargs: False
