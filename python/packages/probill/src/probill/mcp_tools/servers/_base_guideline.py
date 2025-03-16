import os


def get_guideline_path(guideline_name: str) -> str:
    return os.path.join(os.path.dirname(__file__), "guidelines", guideline_name)


def get_guideline_file(guideline_name: str) -> str:
    return os.path.join(get_guideline_path(guideline_name), "guideline.json")


def get_guideline_files(guideline_name: str) -> list[str]:
    return [
        os.path.join(get_guideline_path(guideline_name), f)
        for f in os.listdir(get_guideline_path(guideline_name))
    ]
