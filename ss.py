import csv
import re
import time

import requests

# ====== НАСТРОЙКИ ======
KEY = "3aa5a2da-c5fa-49da-a48a-c0ffbd843b9b"          # вставьте сюда ключ 2GIS
ГОРОД_ПО_УМОЛЧАНИЮ = "Талдыкорган"
СТРАНИЦ_НА_КАТЕГОРИЮ = 3  # 1 страница = до 10 заведений

# Бизнесы, которым сайт реально нужен (клиенты ищут их в интернете)
КАТЕГОРИИ = [
    "салон красоты",
    "барбершоп",
    "ногтевая студия маникюр",
    "косметолог",
    "стоматология",
    "фитнес клуб",
    "фотостудия",
    "организация праздников",
    "ремонт квартир",
    "ресторан",
]
# =======================


def только_цифры(номер):
    return re.sub(r"\D", "", номер)


def мобильный_казахстан(номер):
    """Возвращает номер вида 7XXXXXXXXXX, если он мобильный (+7 7xx...), иначе None."""
    д = только_цифры(номер)
    if len(д) == 11 and д[0] == "8":
        д = "7" + д[1:]
    if len(д) == 11 and д.startswith("77"):
        return д
    return None


ввод = input(f"Город (Enter = {ГОРОД_ПО_УМОЛЧАНИЮ}): ").strip()
ГОРОД = ввод or ГОРОД_ПО_УМОЛЧАНИЮ

найдено = {}  # id заведения -> данные, чтобы не было повторов

for категория in КАТЕГОРИИ:
    print(f"Ищу: {категория}...")
    for страница in range(1, СТРАНИЦ_НА_КАТЕГОРИЮ + 1):
        try:
            ответ = requests.get(
                "https://catalog.api.2gis.com/3.0/items",
                params={
                    "q": f"{категория} {ГОРОД}",
                    "fields": "items.contact_groups,items.address_name",
                    "page": страница,
                    "page_size": 10,
                    "key": KEY,
                },
                timeout=20,
            ).json()
        except Exception as e:
            print("  Ошибка запроса:", e)
            break

        места = ответ.get("result", {}).get("items", [])
        if not места:
            # если пусто, покажем, что ответил сервер (помогает понять проблему с ключом)
            if страница == 1:
                print("  Ничего не найдено. Ответ сервера:", ответ.get("meta", ответ))
            break

        for место in места:
            id_ = место.get("id")
            if id_ in найдено:
                continue

            контакты = [
                к
                for группа in место.get("contact_groups", [])
                for к in группа.get("contacts", [])
            ]
            типы = {к.get("type") for к in контакты}

            if "website" in типы:
                continue  # сайт уже есть, пропускаем

            телефоны = [к["text"] for к in контакты if к.get("type") == "phone"]
            if not телефоны:
                continue  # без телефона лид бесполезен

            мобильные = [м for м in (мобильный_казахстан(т) for т in телефоны) if м]
            whatsapp = f"https://wa.me/{мобильные[0]}" if мобильные else ""
            instagram = any(k.get("type") == "instagram" for k in контакты)

            найдено[id_] = {
                "категория": категория,
                "название": место.get("name", ""),
                "адрес": место.get("address_name", ""),
                "телефоны": "; ".join(телефоны),
                "мобильный": bool(мобильные),
                "whatsapp": whatsapp,
                "instagram": "да" if instagram else "",
            }
        time.sleep(0.5)  # небольшая пауза между запросами

# Сначала те, у кого есть мобильный (можно писать в WhatsApp)
результат = sorted(найдено.values(), key=lambda x: (not x["мобильный"], x["категория"]))

with open("leads.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["Категория", "Название", "Адрес", "Телефоны", "WhatsApp", "Есть Instagram", "Статус"])
    for р in результат:
        w.writerow([
            р["категория"], р["название"], р["адрес"],
            р["телефоны"], р["whatsapp"], р["instagram"], "",
        ])

print()
print(f"=== Найдено без сайта: {len(результат)} ===")
for р in результат:
    print(f"[{р['категория']}] {р['название']} | {р['адрес']}")
    print(f"    тел: {р['телефоны']}")
    if р["whatsapp"]:
        print(f"    WhatsApp: {р['whatsapp']}")

print()
print("Всё сохранено в leads.csv (колонка «Статус» пустая, пишите туда: написал / ответил / отказ).")
