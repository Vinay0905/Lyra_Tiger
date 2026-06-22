import os
import subprocess
import pyperclip
from src.config import settings

class DevToolsClient:
    """
    Safely executes developer operations: clipboard read,
    writing boilerplate files, and launching applications inside approved folders.
    """
    def read_clipboard(self) -> str:
        print("[Dev Skill] Reading clipboard contents...")
        try:
            return pyperclip.paste()
        except Exception as e:
            return f"Error reading clipboard: {str(e)}"

    def _is_path_approved(self, path: str) -> bool:
        abs_target = os.path.abspath(path)
        for approved_dir in settings.approved_workspace_paths:
            if abs_target.startswith(approved_dir):
                return True
        return False

    def write_scaffold(self, filename: str, content: str, folder_path: str) -> str:
        target_path = os.path.join(folder_path, filename)
        
        if not self._is_path_approved(target_path):
            raise PermissionError(
                f"Security block: path '{target_path}' is not within approved workspace paths."
            )
            
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"[Dev Skill] Scaffold file created: {target_path}")
        return target_path

    def launch_vs_code(self, folder_path: str):
        if not self._is_path_approved(folder_path):
            raise PermissionError("Access Denied: Path folder not approved.")
            
        print(f"[Dev Skill] Launching VS Code for: {folder_path}")
        # subprocess run without shell=True to prevent cmd injections
        subprocess.Popen(["code", folder_path], shell=False)
