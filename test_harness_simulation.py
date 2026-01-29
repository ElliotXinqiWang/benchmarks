"""模拟生成的harness文件 - 仅包含导入部分用于测试"""

import sys, os
import importlib

# 动态导入路径
# harness中会使用: sys.path.insert(0, "{self.working_dir}")
# 其中 self.working_dir = "/workspace/astropy"
sys.path.insert(0, "/workspace/astropy")

# ========================================
# 导入代码部分 (由 _generate_import_code 生成)
# target: "astropy/units/core.py:_condition_arg"
# 会被识别为相对路径格式，转换为模块格式: "astropy.units.core"
# ========================================
# Import from path (converted to module format)
import sys
import os
import importlib

module_name = "astropy.units.core"
target_func_name = "_condition_arg"

print("[FuzzHypo] Importing: {}:{}".format(module_name, target_func_name))
print(f"  cwd: {os.getcwd()}, sys.path[0]: {sys.path[0] if sys.path else 'empty'}")

try:
    _module = importlib.import_module(module_name)
    target_func = getattr(_module, target_func_name)
    print(f"[FuzzHypo] OK: imported from {module_name}")
except Exception as e:
    print(f"[FuzzHypo] FAILED: {e}")
    import traceback
    traceback.print_exc()
    raise ImportError(f"Failed to import {target_func_name} from {module_name}: {e}")

print(f"\n✓ 成功导入函数: {target_func}")
print(f"  函数类型: {type(target_func)}")
print(f"  函数位置: {target_func.__module__}")
