"""Print the CUDA devices CuPy can see, as one line of JSON.

Studio runs this file as a script in a subprocess (``etalon/studio/system.py``):
``import cupy`` takes about a second, loads CUDA into whichever process does it,
and a broken driver can hang or crash that process. It imports nothing from
etalon, so the subprocess stays light.

Output: ``{"cupy_status": "ok" | "missing" | "error", "cupy_detail": str | null,
"devices": [{"index", "name", "memory_bytes", "compute_capability"}]}``.
"""

import json
import warnings


def probe() -> dict[str, object]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # e.g. "CUDA path could not be detected"
            import cupy
    except ImportError:
        return {"cupy_status": "missing", "cupy_detail": None, "devices": []}
    except Exception as error:  # a broken install raises more than ImportError
        return {"cupy_status": "error", "cupy_detail": _describe(error), "devices": []}
    try:
        count = cupy.cuda.runtime.getDeviceCount()
        devices = []
        for index in range(count):
            props = cupy.cuda.runtime.getDeviceProperties(index)
            name = props["name"]
            devices.append(
                {
                    "index": index,
                    "name": name.decode() if isinstance(name, bytes) else str(name),
                    "memory_bytes": int(props["totalGlobalMem"]),
                    "compute_capability": f"{props['major']}.{props['minor']}",
                }
            )
    except Exception as error:  # no driver, no device, driver too old
        return {"cupy_status": "error", "cupy_detail": _describe(error), "devices": []}
    return {"cupy_status": "ok", "cupy_detail": None, "devices": devices}


def _describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


if __name__ == "__main__":
    print(json.dumps(probe()))
