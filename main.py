import sys
import nikkei_utils
import kabutan_utils

def print_usage_and_exit():
    print("使用法: python main.py <ユーザーハンドル> <パスワード> <モード>")
    sys.exit(1)

def main():
    if len(sys.argv) != 4:
        print_usage_and_exit()

    user_handle, user_password, mode = sys.argv[1], sys.argv[2], sys.argv[3]

    if mode not in ["nikkei", "kabutan"]:
        print_usage_and_exit()
    
    if mode == "nikkei":
        nikkei_utils.post(user_handle, user_password)
    elif mode == "kabutan":
        kabutan_utils.post(user_handle, user_password)

if __name__ == "__main__":
    main()
