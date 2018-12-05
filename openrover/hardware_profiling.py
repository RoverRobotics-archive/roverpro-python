import time

from matplotlib.axes import Axes
import numpy as np
import seaborn as sns

from openrover import OpenRover

sns.set(style="darkgrid")
import pandas as pd

motor_data = pd.DataFrame


def profile_motor(rover, x_gridnum, samples_each_x, left=True, right=True):
    efforts = []
    currents = []
    total_battery_current = []
    intervals = []
    inverse_intervals = []
    sides = []

    for effort in np.linspace(-1, +1, num=x_gridnum):
        rover.set_motor_speeds(
            effort if left else 0, effort if right else 0, 0)

        for i in range(samples_each_x):
            rover.set_fan_speed(240)
            rover.send_speed()

            if left:
                total_battery_current.append(rover.get_data_synchronous(0))
                efforts.append(effort)
                sides.append('left')
                currents.append(rover.get_data_synchronous(10) / 34)
                interval = rover.get_data_synchronous(28)
                intervals.append(interval)
                inverse_intervals.append(0 if interval == 0 else 1 / interval)

            if right:
                total_battery_current.append(rover.get_data_synchronous(0))
                efforts.append(effort)
                sides.append('right')
                currents.append(rover.get_data_synchronous(12) / 34)
                interval = rover.get_data_synchronous(30)
                intervals.append(interval)
                inverse_intervals.append(0 if interval == 0 else 1 / interval)

    return pd.DataFrame({'effort': efforts, 'interval': intervals, 'inverse_interval': inverse_intervals, 'current': currents, 'side': sides, 'total_battery_current':total_battery_current})


effort_levels = 51
samples_each = 3

with OpenRover() as rover:
    p = profile_motor(rover, effort_levels, samples_each)
    p.to_csv('data_{}x{}.csv'.format(effort_levels, samples_each))

# b = sns.lineplot(x="effort", y="current", data=p, hue='side')
# b.figure.savefig('effort_vs_current_{}x{}.svg'.format(effort_levels, samples_each))
# b.figure.clear()

a = sns.lineplot(x="effort", y="inverse_interval", data=p, hue='side')
a.figure.savefig('effort_vs_wheel_speed_{}x{}.svg'.format(effort_levels, samples_each))
a.figure.clear()

# with OpenRover() as rover:
#     p = profile_motor(rover, effort_levels, samples_each, right=False)
#     p = p.append(profile_motor(rover, effort_levels, samples_each, left=False))
#     a = sns.lineplot(x="effort", y="total_battery_current", data=p, hue='side')
#     a.figure.savefig('effort_vs_supply_current{}x{}.svg'.format(effort_levels, samples_each))
