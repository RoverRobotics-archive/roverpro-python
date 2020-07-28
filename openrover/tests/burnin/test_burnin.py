import logging
from time import monotonic

import pytest
import trio

from openrover import open_rover

logger = logging.getLogger(__file__)


async def control_robot(rover, left, right, flipper, duration):
    rover.set_motor_speeds(left, right, flipper)
    logger.info(
        f"Sending command left motor: {left} right motor: {right} flipper: {flipper} duration"
        f" {duration} seconds..."
    )
    t1 = monotonic()
    while True:
        rover.send_speed()
        await trio.sleep(0.5)
        left_motor_encoder_interval = await rover.get_data(28)
        right_motor_encoder_interval = await rover.get_data(30)
        left_motor_temperature = await rover.get_data(20)
        right_motor_temperature = await rover.get_data(22)
        if t1 + duration < monotonic():
            break

    logger.info(
        f" left motor encoder interval: {left_motor_encoder_interval} right motor encoder"
        f" interval: {right_motor_encoder_interval} left motor temperature:"
        f" {left_motor_temperature} right motor temperature {right_motor_temperature}"
    )

    errs = []
    if left != 0 and left_motor_encoder_interval == 0:
        errs.append("left motor speed error")
    if right != 0 and right_motor_encoder_interval == 0:
        errs.append("right motor speed error")
    if left_motor_temperature > 200:
        errs.append("left motor temperature too high")
    if right_motor_temperature > 200:
        errs.append("right motor temperature too high")

    if errs:
        err = ";".join(errs)
        logger.error(err)
        raise RuntimeError(err)


@pytest.mark.burnin
async def test_burnin():
    t1 = monotonic()
    async with open_rover() as rover:
        logger.info("burn test procedure starting!")

        await trio.sleep(1)
        version = await rover.get_data(40)
        logger.info(f"rover firmware version {version}")

        # for testing, we could set x =0.02 or something less than 1 to speed up the process
        # x=0.02
        # for actual use of burn test script, the scale factor x should be set to 1
        x = 1

        # 1. Forward 35% speed for 30 sec
        # run 30 seconds left motor 350, right motor 350, fan 240
        await control_robot(rover, 0.35, 0.35, 0, 30 * x)
        # 2. Stop for 0.5 sec
        await control_robot(rover, 0, 0, 0, 0.5 * x)
        # 3. Left turn for 2 sec
        await control_robot(rover, -0.3, 0.3, 0, 2 * x)
        # 4. Stop for 0.5 sec
        await control_robot(rover, 0, 0, 0, 0.5 * x)
        # 5. Right turn for 2 sec
        await control_robot(rover, 0.3, -0.3, 0, 2 * x)
        # 6. Stop for 0.5 sec
        await control_robot(rover, 0, 0, 0, 0.5 * x)
        # 7. Forward 35% speed for 30 sec
        await control_robot(rover, 0.35, 0.35, 0, 30 * x)
        # 8. Flipper up for 6 sec
        await control_robot(rover, 0, 0, 0.35, 6 * x)
        # 9. Flipper down for 6 sec
        await control_robot(rover, 0, 0, -0.35, 6 * x)
        # 10. Flipper up for 6 sec
        await control_robot(rover, 0, 0, 0.35, 6 * x)
        # 11. Flipper down for 6 sec
        await control_robot(rover, 0, 0, -0.35, 6 * x)
        # 12. Flipper up for 1.5 sec
        await control_robot(rover, 0, 0, 0.35, 1.5 * x)
        # 13. Forward 35% speed for 60 sec
        await control_robot(rover, 0.35, 0.35, 0, 60 * x)
        # 14. Stop for 0.5 sec
        await control_robot(rover, 0, 0, 0, 0.5 * x)
        # 15. Backward 35% speed for 30 sec
        await control_robot(rover, -0.35, -0.35, 0, 30 * x)
        # 16. Stop for 10 sec
        await control_robot(rover, 0, 0, 0, 10 * x)
        # another loop starts
        # 15 times loop, full speed
        for n in range(0, 15):
            # 1. Forward 100% speed for 30 sec
            await control_robot(rover, 1, 1, 0, 30 * x)
            # 2. Stop for 0.5 sec
            await control_robot(rover, 0, 0, 0, 0.5 * x)
            # 3. Left turn for 2 sec
            await control_robot(rover, -0.3, 0.3, 0, 2 * x)
            # 4. Stop for 0.5 sec
            await control_robot(rover, 0, 0, 0, 0.5 * x)
            # 5. Right turn for 2 sec
            await control_robot(rover, 0.3, -0.3, 0, 2 * x)
            # 6. Stop for 0.5 sec
            await control_robot(rover, 0, 0, 0, 0.5 * x)
            # 7. Forward 60% speed for 30 sec
            await control_robot(rover, 0.6, 0.6, 0, 30 * x)
            # 8. Flipper up for 6 sec
            await control_robot(rover, 0, 0, 0.8, 6 * x)
            # 9. Flipper down for 6 sec
            await control_robot(rover, 0, 0, -0.8, 6 * x)
            # 10. Flipper up for 6 sec
            await control_robot(rover, 0, 0, 0.8, 6 * x)
            # 11. Flipper down for 6 sec
            await control_robot(rover, 0, 0, -0.8, 6 * x)
            # 12. Flipper up for 1.5 sec
            await control_robot(rover, 0, 0, 0.8, 1.5 * x)
            # 13. Forward 60% speed for 60 sec
            await control_robot(rover, 0.6, 0.6, 0, 60 * x)
            # 14. Stop for 0.5 sec
            await control_robot(rover, 0, 0, 0, 0.5 * x)
            # 15. Backward 60% speed for 30 sec
            await control_robot(rover, 0.6, 0.6, 0, 30 * x)
            # 16. Stop for 10 sec
            await control_robot(rover, 0, 0, 0, 10 * x)
            # loop ends
        t2 = monotonic()
        logging.info(f"finished in {t2 - t1} seconds")
        # close the file if needed
        # do something to indicate the burn test is finished
        logging.info("burn test finished successfully!")
