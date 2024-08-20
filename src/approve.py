from datetime import datetime
import json
import os
import secrets
from typing import Optional
from click import confirm
from pydantic import BaseModel


class PrivateCredential(BaseModel):
    require_confirm: bool = False
    username: str
    password: str


cred_dict: dict[str, PrivateCredential] = dict()

if os.path.exists("local.credential.json"):
    with open("local.credential.json", "rb") as f:
        result = json.load(f)
        assert isinstance(result, list)
        for v in result:
            passphrase_set = v["passphrase"]
            assert passphrase_set != ""  # 请勿设置passphrase为空字符串
            passphrase = (
                passphrase_set if passphrase_set is not None else secrets.token_hex(16)
            )
            cred = PrivateCredential(**v)
            cred_dict[passphrase] = cred
            if passphrase_set is None:
                print(f"Generated passphrase for '{cred.username}': '{passphrase}'")


def get_credential_from_passphrase(passphrase: str) -> Optional[PrivateCredential]:
    result = cred_dict.get(passphrase)
    if result is None:
        return None
    if result.require_confirm:
        try:
            if not confirm(
                f"[{datetime.now().strftime("%H:%M:%S")}] Allow access for '{result.username}'?",
                show_default=True,
                default=True,
            ):
                return None
        except:
            return None
    print(
        f"[{datetime.now().strftime("%H:%M:%S")}] Approved access for '{result.username}'."
    )
    return result
