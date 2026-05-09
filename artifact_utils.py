import os


def _artifact_dir():
    return os.environ.get("ARTIFACT_DIR", "tmp")


def save_results(models):
    folder_path = _artifact_dir()
    file_path = os.path.join(folder_path, "previous_result.txt")

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    with open(file_path, "w") as file:
        for model in models:
            file.write(f"{model[0]}\n")


def load_previous_results():
    folder_path = _artifact_dir()
    file_path = os.path.join(folder_path, "previous_result.txt")

    try:
        with open(file_path, "r") as file:
            return [line.strip() for line in file]
    except FileNotFoundError:
        return []
