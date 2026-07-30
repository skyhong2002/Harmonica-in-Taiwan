#!/usr/bin/env python3
"""Configure and publish the public Google Form used by /submit/."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


DEFAULT_FORM_ID = "1yU36b4wOEH2nUXNicFEdWTWYjAUjdTnNEE9Q45lQCP8"
RESPONDER_URI = "https://docs.google.com/forms/d/e/1FAIpQLSe8hVzkjRzG7gk5uj_zVwF4mYHV61G5164J0pNfctpPcdid9Q/viewform"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CONFIG_PATH = PROJECT_ROOT / "data" / "submission-form-public.json"
FORM_TITLE = "臺灣口琴觀測站資料回報"
FORM_DESCRIPTION = (
    "回報公開口琴活動、社團、演奏者、教學單位、場館與社群來源。"
    "請只填公開可查資料，不要提供私人電話、私人信箱、未公開群組、會員資料或憑證。"
    "臺灣口琴音樂節期間也歡迎回報活動異動與新公開來源。"
)


def choice_item(
    title: str,
    options: list[str],
    *,
    required: bool,
    description: str = "",
    choice_type: str = "RADIO",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "title": title,
        "questionItem": {
            "question": {
                "required": required,
                "choiceQuestion": {
                    "type": choice_type,
                    "options": [{"value": option} for option in options],
                    "shuffle": False,
                },
            }
        },
    }
    if description:
        item["description"] = description
    return item


def text_item(
    title: str,
    *,
    required: bool,
    paragraph: bool = False,
    description: str = "",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "title": title,
        "questionItem": {
            "question": {
                "required": required,
                "textQuestion": {"paragraph": paragraph},
            }
        },
    }
    if description:
        item["description"] = description
    return item


FORM_ITEMS = [
    choice_item(
        "回報類型",
        [
            "新增來源或社團",
            "修正既有資料",
            "新增活動、比賽或補助資訊",
            "移除或停止收錄",
        ],
        required=True,
    ),
    text_item(
        "名稱",
        required=True,
        description="請填社團、團體、演奏者、活動、場館或公開來源的名稱。",
    ),
    text_item(
        "主要公開來源 URL",
        required=True,
        description="請提供官方網站、公開社群頁、公開貼文、活動頁、售票頁或公開頻道。",
    ),
    text_item(
        "目前的觀測站頁面或 public_id",
        required=False,
        description="修改或移除資料時請填；新增資料可留白。",
    ),
    text_item(
        "希望網站最後怎麼呈現",
        required=True,
        paragraph=True,
        description="可包含建議名稱、分類、地區、日期、地點、公開連結，以及是否需要監看更新。",
    ),
    text_item(
        "活動日期、地點與主辦單位",
        required=False,
        paragraph=True,
        description="回報活動、比賽、講座、工作坊、徵件或補助資訊時請填。",
    ),
    text_item(
        "補充公開來源",
        required=False,
        paragraph=True,
        description="每行一個公開 URL；沒有可留白。",
    ),
    choice_item(
        "公開資料確認",
        ["我確認以上內容都是公開可查資料，且未提供私人或敏感資訊。"],
        required=True,
        choice_type="CHECKBOX",
    ),
]

KIND_LABELS = {
    "add-source": "新增來源或社團",
    "correct": "修正既有資料",
    "event": "新增活動、比賽或補助資訊",
    "remove": "移除或停止收錄",
}
PUBLIC_ENTRY_KEYS = {
    "回報類型": "kind",
    "名稱": "name",
    "主要公開來源 URL": "source",
    "目前的觀測站頁面或 public_id": "page",
    "希望網站最後怎麼呈現": "desired",
    "活動日期、地點與主辦單位": "event",
    "補充公開來源": "extra",
}


def item_titles(items: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("title") or "") for item in items]


def public_entry_ids(items: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        key = PUBLIC_ENTRY_KEYS.get(str(item.get("title") or ""))
        question_id = item.get("questionItem", {}).get("question", {}).get("questionId")
        if key and question_id:
            result[key] = str(question_id)
    missing = sorted(set(PUBLIC_ENTRY_KEYS.values()) - set(result))
    if missing:
        raise ValueError(f"Published form is missing public entry IDs: {', '.join(missing)}")
    return result


def write_public_config(form: dict[str, Any]) -> dict[str, Any]:
    config = {
        "entryIds": public_entry_ids(form.get("items", [])),
        "kindLabels": KIND_LABELS,
        "responderUri": form.get("responderUri") or RESPONDER_URI,
    }
    PUBLIC_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return config


def build_requests(existing_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = [
        {
            "updateFormInfo": {
                "info": {"title": FORM_TITLE, "description": FORM_DESCRIPTION},
                "updateMask": "title,description",
            }
        }
    ]
    requests.extend(
        {"deleteItem": {"location": {"index": index}}}
        for index in range(len(existing_items) - 1, -1, -1)
    )
    requests.extend(
        {"createItem": {"item": item, "location": {"index": index}}}
        for index, item in enumerate(FORM_ITEMS)
    )
    return requests


def load_credentials(token_file: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise SystemExit(
            "google-api-python-client credentials are unavailable; run with the Hermes Google Workspace venv"
        ) from exc

    credentials = Credentials.from_authorized_user_file(str(token_file))
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        token_file.write_text(credentials.to_json(), encoding="utf-8")
        token_file.chmod(0o600)
    if not credentials.valid:
        raise SystemExit(f"Google OAuth credentials are invalid: {token_file}")
    return credentials


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--form-id", default=DEFAULT_FORM_ID)
    parser.add_argument(
        "--token-file",
        type=Path,
        default=Path(
            os.environ.get(
                "HARMONICA_GOOGLE_TOKEN",
                Path.home() / ".hermes/profiles/bamboo/harmonica-observe-google-token.json",
            )
        ),
    )
    parser.add_argument(
        "--replace-items",
        action="store_true",
        help="Replace existing questions when they differ from the checked-in form specification.",
    )
    args = parser.parse_args()

    if not args.token_file.exists():
        raise SystemExit(f"Google OAuth token not found: {args.token_file}")

    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise SystemExit(
            "google-api-python-client is unavailable; run with the Hermes Google Workspace venv"
        ) from exc

    credentials = load_credentials(args.token_file)
    forms = build("forms", "v1", credentials=credentials, cache_discovery=False)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)

    form = forms.forms().get(formId=args.form_id).execute()
    existing_items = form.get("items", [])
    expected_titles = item_titles(FORM_ITEMS)
    current_titles = item_titles(existing_items)

    if current_titles != expected_titles:
        if not args.replace_items:
            print(
                json.dumps(
                    {
                        "status": "items_differ",
                        "currentTitles": current_titles,
                        "expectedTitles": expected_titles,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            print("Re-run with --replace-items after reviewing the differences.", file=sys.stderr)
            return 2
        forms.forms().batchUpdate(
            formId=args.form_id,
            body={"requests": build_requests(existing_items)},
        ).execute()
    else:
        forms.forms().batchUpdate(
            formId=args.form_id,
            body={
                "requests": [
                    {
                        "updateFormInfo": {
                            "info": {"title": FORM_TITLE, "description": FORM_DESCRIPTION},
                            "updateMask": "title,description",
                        }
                    }
                ]
            },
        ).execute()

    drive.files().update(
        fileId=args.form_id,
        body={"name": FORM_TITLE},
        fields="id,name",
    ).execute()
    forms.forms().setPublishSettings(
        formId=args.form_id,
        body={
            "publishSettings": {
                "publishState": {
                    "isPublished": True,
                    "isAcceptingResponses": True,
                }
            },
            "updateMask": "publish_state",
        },
    ).execute()

    updated = forms.forms().get(formId=args.form_id).execute()
    if updated.get("responderUri") != RESPONDER_URI:
        raise SystemExit(
            "Published responder URI differs from the checked-in site configuration: "
            f"{updated.get('responderUri')!r}"
        )
    public_config = write_public_config(updated)
    output = {
        "formId": updated.get("formId"),
        "title": updated.get("info", {}).get("title"),
        "itemTitles": item_titles(updated.get("items", [])),
        "linkedSheetId": updated.get("linkedSheetId"),
        "publishSettings": updated.get("publishSettings"),
        "responderUri": updated.get("responderUri"),
        "publicEntryIds": public_config["entryIds"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
