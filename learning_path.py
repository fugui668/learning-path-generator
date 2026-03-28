# 向后兼容 shim，保持 `python3 learning_path.py --demo` 等命令仍可用
from learning_path.cli import main

if __name__ == "__main__":
    main()
