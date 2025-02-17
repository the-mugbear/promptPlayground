class Transformation:
    id: str  # short unique ID
    name: str  # human-readable
    description: str  # optional

    def apply(self, prompt: str, params: dict = None) -> str:
        raise NotImplementedError
