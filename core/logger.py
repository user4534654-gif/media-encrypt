import os
import sys
import time
import datetime
import traceback
import functools
class LiveDebugger:
    logs = []
    last_diagnostic = None
    @classmethod
    def log(cls, action, details, level="INFO", module=None, extra=None):
        if isinstance(level, (list, tuple, set)):
            mod_items = [str(x) for x in level]
            if not module:
                module = ", ".join(mod_items)
            level = "INFO"
        elif not isinstance(level, str):
            level = str(level)
        level_str = level.upper() if level else "INFO"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        mod_str = f"[{module}] " if module else ""
        extra_str = f" | {extra}" if extra else ""
        msg = f"[{timestamp}] [GDB-DBGR] [{level_str:<5}] {mod_str}{action.upper()} - {details}{extra_str}"
        cls.logs.append(msg)
        print(msg)
        sys.stdout.flush()
    @classmethod
    def trace(cls, module_name="APP"):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                fn_name = func.__name__
                clean_args = []
                for a in args:
                    if isinstance(a, (bytes, bytearray)) and len(a) > 64:
                        clean_args.append(f"<bytes len={len(a)}>")
                    else:
                        clean_args.append(repr(a))
                clean_kwargs = {k: (f"<bytes len={len(v)}>" if isinstance(v, (bytes, bytearray)) and len(v) > 64 else repr(v)) for k, v in kwargs.items()}
                arg_str = ", ".join(clean_args + [f"{k}={v}" for k, v in clean_kwargs.items()])
                cls.log("ENTER", f"-> {fn_name}({arg_str})", level="TRACE", module=module_name)
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    elapsed = time.time() - start_time
                    cls.log("EXIT", f"<- {fn_name} completed in {elapsed:.3f}s", level="TRACE", module=module_name)
                    return result
                except Exception as e:
                    elapsed = time.time() - start_time
                    cls.log("CRASH", f"<- {fn_name} failed after {elapsed:.3f}s: {e}", level="ERROR", module=module_name)
                    cls.analyze_exception(e, module_name=module_name, func_name=fn_name)
                    raise
            return wrapper
        return decorator
    @classmethod
    def analyze_exception(cls, e, module_name=None, func_name=None):
        exc_type = type(e).__name__
        exc_msg = str(e)
        raw_tb = traceback.format_exc()
        tb_list = traceback.extract_tb(e.__traceback__)
        failing_frame_info = None
        failing_py_frame = None
        curr_tb = e.__traceback__
        while curr_tb:
            frame = curr_tb.tb_frame
            filename = frame.f_code.co_filename
            if "site-packages" not in filename and "lib\\" not in filename and "lib/" not in filename:
                failing_py_frame = frame
            curr_tb = curr_tb.tb_next
        if not failing_py_frame and e.__traceback__:
            failing_py_frame = e.__traceback__.tb_frame
        if tb_list:
            last_entry = tb_list[-1]
            file_path = os.path.basename(last_entry.filename)
            line_no = last_entry.lineno
            func_in_tb = last_entry.name
            code_line = last_entry.line or "N/A"
        else:
            file_path = "Unknown"
            line_no = 0
            func_in_tb = func_name or "Unknown"
            code_line = "N/A"
        local_vars = {}
        if failing_py_frame:
            for k, v in failing_py_frame.f_locals.items():
                if k.startswith("__"):
                    continue
                try:
                    str_v = repr(v)
                    if len(str_v) > 120:
                        str_v = str_v[:117] + "..."
                    local_vars[k] = str_v
                except Exception:
                    local_vars[k] = "<unrepresentable>"
        root_cause, suggestion = cls._diagnose_root_cause(exc_type, exc_msg, local_vars, code_line)
        divider = "=" * 80
        report_lines = [
            divider,
            "[GDB-DBGR] CRASH DIAGNOSTIC REPORT",
            f"Exception:  {exc_type}: {exc_msg}",
            f"Location:   {file_path}:{line_no} in function '{func_in_tb}'",
            f"Code Line:  {code_line}",
            f"Root Cause: {root_cause}",
            f"Fix Hint:   {suggestion}",
            "Local Variables Snapshot:"
        ]
        if local_vars:
            for k, v in local_vars.items():
                report_lines.append(f"  * {k} = {v}")
        else:
            report_lines.append("  (No local variables captured)")
        report_lines.append(divider)
        formatted_report = "\n".join(report_lines)
        print("\n" + formatted_report + "\n")
        sys.stdout.flush()
        cls.last_diagnostic = {
            "error_type": exc_type,
            "error_message": exc_msg,
            "file": file_path,
            "line": line_no,
            "function": func_in_tb,
            "code_line": code_line,
            "root_cause": root_cause,
            "suggestion": suggestion,
            "local_vars": local_vars,
            "traceback": raw_tb
        }
        cls.logs.append(formatted_report)
        return cls.last_diagnostic
    @classmethod
    def _diagnose_root_cause(cls, exc_type, exc_msg, local_vars, code_line):
        msg_lower = exc_msg.lower()
        if "ffmpeg" in msg_lower or "ffprobe" in msg_lower:
            return (
                "FFmpeg binary execution error or missing dependency.",
                "Verify 'imageio-ffmpeg' is installed or FFmpeg is present in system PATH."
            )
        elif "grid" in msg_lower or "columns" in msg_lower or "rows" in msg_lower or "dimension" in msg_lower or "division by zero" in msg_lower:
            return (
                "Grid calculation mismatch or invalid row/column dimensions for media size.",
                "Ensure columns and rows > 1 and dimensions are divisible or large enough for chosen layout."
            )
        elif "key" in msg_lower or "seed" in msg_lower or "unscramble" in msg_lower or "valueerror" in msg_lower and "base" in msg_lower:
            return (
                "Key/seed format corruption or hash parsing error.",
                "Verify key string format (e.g. 10x10|seed|mode) without extra leading/trailing whitespace."
            )
        elif "permission" in msg_lower or "denied" in msg_lower or "access" in msg_lower:
            return (
                "Operating system file permission denied.",
                "Check disk write permissions for media_encrypt_vault directory."
            )
        elif "filenotfounderror" in msg_lower or "no such file" in msg_lower:
            return (
                "Specified source file or directory path does not exist.",
                "Verify source file location and check that file was not moved or deleted."
            )
        elif "format string" in msg_lower or "list.__format__" in msg_lower or "unsupported format" in msg_lower:
            return (
                "Invalid data type or string formatting argument error.",
                "Verify logging parameters and argument types match string formatting specifications."
            )
        elif "codec" in msg_lower or "container format" in msg_lower or "encoder" in msg_lower or "unsupported codec" in msg_lower:
            return (
                "Media container or codec incompatibility.",
                "Try setting container format and video/audio codec options to 'Auto'."
            )
        else:
            return (
                f"Unhandled {exc_type} during execution step.",
                "Inspect local variables snapshot and stack traceback details above."
            )
    @classmethod
    def save_to_file(cls):
        try:
            filename = "media_encrypt_debug_log.txt"
            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            filepath = os.path.join(downloads, filename) if os.path.exists(downloads) else os.path.abspath(filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(cls.logs))
            cls.log("SAVE_LOG", f"Saved debug log file to: {filepath}", level="INFO", module="LOGGER")
            return filepath
        except Exception as e:
            print(f"Error saving debug log: {e}")
            return None
