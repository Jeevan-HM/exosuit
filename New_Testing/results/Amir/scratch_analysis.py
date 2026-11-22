import pandas as pd
import matplotlib.pyplot as plt
import os

filepath = r"c:\Users\Jahnav Rokalaboina\ASU Dropbox\Jahnav Rokalaboina\Exosuit & RL Project\New Exosuit\New_Testing\results\Amir\RL_TrainingData_Amir_EXOACTIVE_RL_inc0_spd0p8_1.csv"
df = pd.read_csv(filepath)

print("Number of rows:", len(df))
print(df[['t1 error', 't2 error', 'kinematic errorA', 'kinematic errorC']].describe())

# plot to an image 
df[['t1 error', 't2 error']].plot()
plt.title("Timing Errors")
plt.savefig("timing_errors_amir.png")
plt.close()

df[['kinematic errorA', 'kinematic errorC']].plot()
plt.title("Kinematic Errors")
plt.savefig("kinematic_errors_amir.png")
plt.close()
