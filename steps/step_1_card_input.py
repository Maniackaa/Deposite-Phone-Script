import asyncio

from adbutils import AdbDevice

from config.bot_settings import press_tab, get_my_loggers


async def insert_card_data(adb_device: AdbDevice, data: dict):
    payment_id = data['payment_id']
    logger = get_my_loggers().bind(payment_id=payment_id, phone_serial=adb_device.serial)
    owner_name = data['owner_name']
    amount = data['amount']
    card_number = data['card_number']
    expired_month = data['expired_month']
    expired_year = data['expired_year']
    cvv = data['cvv']
    logger.debug(f'Ввожу данные карты {data}')
    adb_device.shell(f'input tap 280 751')
    await asyncio.sleep(1)
    adb_device.shell(f'input text {amount}')
    await asyncio.sleep(1)
    adb_device.shell(f'input tap 550 1550')
    adb_device.shell(f'input tap 550 1360')
    await asyncio.sleep(10)
    adb_device.shell(f'input tap 77 1380')
    await asyncio.sleep(0.5)
    adb_device.shell(f'input tap 330 590')
    adb_device.shell(press_tab)
    await asyncio.sleep(1)
    adb_device.shell(f'input text {card_number}')
    adb_device.shell(press_tab)
    await asyncio.sleep(1)
    adb_device.shell(f'input text {expired_month}{expired_year}')
    await asyncio.sleep(1)
    adb_device.shell(press_tab)
    await asyncio.sleep(1)
    adb_device.shell(f'input text {cvv}')
    await asyncio.sleep(0.5)
    adb_device.shell(f'input tap 550 1477')
    logger.debug('Данные введены')