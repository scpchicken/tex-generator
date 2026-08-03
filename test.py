import os
import sys
import subprocess
from pathlib import Path

def run_syntax_tests():
    test_dir = Path("test")

    if not test_dir.exists() or not test_dir.is_dir():
        print("Error: 'test/' directory not found.")
        sys.exit(1)

    # Dynamically find all .c files inside test/ and all its subdirectories
    test_files = sorted(test_dir.rglob("*.c"))

    if not test_files:
        print("No .c test files found in 'test/' directory.")
        return

    print(f"Found {len(test_files)} test file(s). Checking syntax...\n")

    passed = 0
    failed = 0

    for c_file in test_files:
        # Generate target .tex path in the same subfolder
        tex_file = c_file.with_suffix(".tex")

        # Run texgen.py on the file using Python's subprocess
        cmd = [sys.executable, "texgen.py", str(c_file), str(tex_file)]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f" [PASS] {c_file} -> {tex_file}")
            passed += 1
        else:
            print(f" [FAIL] {c_file}")
            # Print the syntax error or exception raised by texgen.py
            error_msg = result.stderr.strip() or result.stdout.strip()
            for line in error_msg.splitlines():
                print(f"        {line}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed.")
    print("=" * 50)

    # Exit with non-zero code if any syntax errors occurred (useful for CI/CD)
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_syntax_tests()