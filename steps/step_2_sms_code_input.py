import asyncio

from adbutils import AdbDevice

from config.bot_settings import get_my_loggers


async def insert_sms_code(adb_device: AdbDevice, data: dict, sms_code: str):
    """
    step_2 - тап перед вводом смс
    step_3 - тап после ввода смс
    """
    logger = get_my_loggers().bind(phone_serial=adb_device.serial)
    step_2_x = data['step_2_x']
    step_2_y = data['step_2_y']
    step_3_x = data['step_3_x']
    step_3_y = data['step_3_y']

    if step_2_x:
        adb_device.shell(f'input tap {step_2_x} {step_2_y}')
        logger.debug(f'Тап {step_2_x} {step_2_y}')
        await asyncio.sleep(1)
    logger.debug(f'Ввожу смс-код: {sms_code}')
    adb_device.shell(f'input text {sms_code}')
    await asyncio.sleep(1)

    if step_3_x:
        adb_device.shell(f'input tap {step_3_x} {step_3_y}')
        logger.debug(f'Тап {step_3_x} {step_3_y}')
        await asyncio.sleep(1)
    logger.debug('Ввод смс закончен')
