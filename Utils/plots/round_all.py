import matplotlib.pyplot as plt
import pandas as pd
import glob

# Read all .txt files
file_list = glob.glob("..\store_results\CHI\omega\*.txt")  # Assumes all files are in the same directory

print(file_list)
# Initialize lists to store concatenated data
# Initialize lists to store data
all_dfs = []

for file in file_list:
    df = pd.read_csv(file, header=None)
    df.columns = ["Round", "Loss", "Macro", "Micro"]
    all_dfs.append((file, df))

# Plot the data
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for file, df in all_dfs:
    axes[0].plot(df["Round"], df["Loss"], label=file)
    axes[1].plot(df["Round"], df["Macro"], label=file)
    axes[2].plot(df["Round"], df["Micro"], label=file)

axes[0].set_title("Round vs Loss")
axes[0].set_xlabel("Round")
axes[0].set_ylabel("Loss")
axes[0].grid()
#axes[0].legend()

axes[1].set_title("Round vs Macro F1")
axes[1].set_xlabel("Round")
axes[1].set_ylabel("Macro F1")
axes[1].grid()
#axes[1].legend()

axes[2].set_title("Round vs Micro F1")
axes[2].set_xlabel("Round")
axes[2].set_ylabel("Micro F1")
axes[2].grid()
#axes[2].legend()

plt.tight_layout()
plt.show()