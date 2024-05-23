import asyncio
import json
from pathlib import Path
from typing import Sequence


from adbutils import AdbDevice, AdbClient
from sqlalchemy import select, delete

from database.db import last_phone_name
from config.bot_settings import BASE_DIR, logger
from database.db import Session, PhoneDB, PhoneDevice


def read_phones():
    """Чтение файла с настройками телефонов"""
    with open(BASE_DIR / 'phones.txt', 'r', encoding='utf-8') as file:
        phone_data = json.load(file)
        return phone_data

# phones = {
#     "Phone_1": "ascksjc",
#     "Phone_2": "asdasfd",
# }
# with open(BASE_DIR / 'phones.txt', 'w') as file:
#     json.dump(phones, file, indent=2)


def prepare_base():
    phone_data = read_phones()
    session = Session(expire_on_commit=False)
    with session:
        q = delete(PhoneDB).where(PhoneDB.serial.notin_(phone_data.values()))
        res = session.execute(q)
        session.commit()

    for name, serial in phone_data.items():
        session = Session(expire_on_commit=False)
        with session:
            q = select(PhoneDB).where(PhoneDB.serial == serial)
            phone = session.execute(q).scalar()
            if phone:
                phone.name = name
                phone.current_status = PhoneDB.PhoneStatus.READY
                session.commit()
            else:
                new_phone = PhoneDB(name=name, serial=serial, current_status=PhoneDB.PhoneStatus.ERROR)
                session.add(new_phone)
                session.commit()


def read_phones_from_db():
    session = Session(expire_on_commit=True)
    with session:
        q = select(PhoneDB)
        res = session.execute(q).scalars().all()
        return res


def get_ready_phones() -> Sequence[PhoneDB]:
    session = Session(expire_on_commit=True)
    with session:
        # q = select(PhoneDB).filter(PhoneDB.current_status == PhoneDB.PhoneStatus.READY)
        q = select(PhoneDB)
        res = session.execute(q).scalars().all()
        return res


def get_phone_from_pk(pk) -> PhoneDB:
    session = Session(expire_on_commit=True)
    with session:
        q = select(PhoneDB).where(PhoneDB.id == pk)
        res = session.execute(q).scalar()
        return res


def get_phone_from_name(name) -> PhoneDB:
    session = Session(expire_on_commit=True)
    with session:
        q = select(PhoneDB).where(PhoneDB.name == name)
        res = session.execute(q).scalar()
        return res


def refresh_phones_condition():
    adb_devices = get_adb_devices()
    serials = [dev.serial for dev in adb_devices]
    print(serials)
    current_phones = read_phones_from_db()
    for phone in current_phones:
        if phone.serial in serials:
            phone.set('is_active', 1)
        else:
            phone.set('is_active', 0)
            phone.set('current_status', PhoneDB.PhoneStatus.ERROR)


async def make_screenshot(device: AdbDevice):
    # SCREEN_FOLDER = Path('/sdcard/DCIM/Screenshots')
    SCREEN_FOLDER = Path('/sdcard/')
    file_path = SCREEN_FOLDER / f'{device.serial}.png'
    print(file_path)
    target_path = BASE_DIR / 'media' / f'{device.serial}.png'
    print(target_path)
    # if target_path.exists():
    #     target_path.unlink()
    device.shell(f'screencap {file_path.as_posix()}')
    await asyncio.sleep(1)
    downloaded = device.sync.pull(file_path.as_posix(), target_path.as_posix())
    print(downloaded)


def get_adb_devices() -> list[AdbDevice]:
    adb_client = AdbClient(host="127.0.0.1", port=5037, socket_timeout=1)
    adb_devices = adb_client.device_list()
    return adb_devices


def get_device_from_serial(serial) -> AdbDevice:
    device_list = get_adb_devices()
    for dev in device_list:
        if dev.serial == serial:
            return dev


def get_active_phones_names() -> list[str]:
    # Фильтрует подключенные телефоны c файла настроек
    active_phones = []
    phone_data = read_phones()
    active_serials = [device.serial for device in get_adb_devices()]
    for phone_num, serial in phone_data.items():
        if serial in active_serials:
            active_phones.append(phone_num)
    return active_phones





def get_next_device_name() -> str:
    # Выдает по очереди телефон
    global last_phone_name
    try:
        active_phones_names = get_active_phones_names()
        logger.debug(f'active_phones: {active_phones_names}')
        count_active = len(active_phones_names)
        if active_phones_names:
            new_phone_name = last_phone_name[0]
            if not last_phone_name or count_active == 1:
                new_phone_name = active_phones_names[0]
            else:
                # Находим следующий живой номер
                for name in active_phones_names:
                    if name > last_phone_name[0]:
                        new_phone_name = name
                        break

            if last_phone_name[0] == new_phone_name:
                new_phone_name = active_phones_names[0]
            last_phone_name[0] = new_phone_name
            logger.debug(f'new last_phone_name: {new_phone_name}')
            return new_phone_name
        logger.debug('Телефонов не найдено')
    except Exception as err:
        raise err


def get_phone_device_from_name(name):
    phone_db = get_phone_from_name(name)
    for adb_device in get_adb_devices():
        if adb_device.serial == phone_db.serial:
            phone: PhoneDevice = PhoneDevice(db=phone_db, device=adb_device)
            return phone


prepare_base()
new_name = get_next_device_name()
phone_device = get_phone_device_from_name(new_name)

