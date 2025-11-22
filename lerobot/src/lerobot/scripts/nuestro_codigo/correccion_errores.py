from huggingface_hub import HfApi

api = HfApi()

# ⚠️ Sustituye esto por tu usuario real de HF
repo_id = "Itsasne/pickup_red_1"

local_path = "/home/ignacio/.cache/huggingface/lerobot/${HF_USER}/pickup_red_1"


# Crear el repo si no existe (tipo dataset)
api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)

# Subir toda la carpeta
api.upload_folder(
    folder_path=local_path,
    repo_id=repo_id,
    repo_type="dataset"
)
