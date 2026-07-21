import os
import datetime

class LiveDebugger:
    logs = []
    
    @classmethod
    def log(cls, action, details, libraries=None):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lib_str = f" | Interaction: {', '.join(libraries)}" if libraries else ""
        msg = f"[{timestamp}] [DEBUG] {action.upper()} - {details}{lib_str}"
        cls.logs.append(msg)
        print(msg)
        
    @classmethod
    def save_to_file(cls):
        try:
            filename = "media_encrypt_debug_log.txt"
            # Try to resolve user's Downloads folder
            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            if os.path.exists(downloads):
                filepath = os.path.join(downloads, filename)
            else:
                filepath = os.path.abspath(filename)
                
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(cls.logs))
            return filepath
        except Exception as e:
            print(f"Error saving debug log: {e}")
            return None
