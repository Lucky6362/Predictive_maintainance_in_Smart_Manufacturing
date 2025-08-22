import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import matplotlib.pyplot as plt

# Set random seed for reproducibility
np.random.seed(42)

# Number of data points to generate (hourly readings for 90 days)
n_samples = 24 * 90

# Start date and time
start_date = datetime(2025, 1, 1, 0, 0, 0)

# Function to generate normal operating data
def generate_normal_data(n_samples):
    data = {
        "timestamp": [start_date + timedelta(hours=i) for i in range(n_samples)],
        "vibration_rms": np.random.normal(0.8, 0.15, n_samples),
        "motor_temp_C": np.random.normal(65, 4, n_samples),
        "spindle_current_A": np.random.normal(15, 1.5, n_samples),
        "rpm": np.random.normal(3000, 200, n_samples),
        "tool_usage_min": np.zeros(n_samples),
        "coolant_temp_C": np.random.normal(30, 2, n_samples),
        "cutting_force_N": np.random.normal(200, 15, n_samples),
        "power_consumption_W": np.random.normal(5000, 400, n_samples),
        "acoustic_level_dB": np.random.normal(75, 3, n_samples),
        "machine_hours_today": np.zeros(n_samples),
        "total_machine_hours": np.zeros(n_samples),
    }

    # Machine usage per day and cumulative hours
    current_day = data["timestamp"][0].day
    daily_hours = random.uniform(6, 15)
    cumulative_hours = 5000

    for i in range(n_samples):
        day = data["timestamp"][i].day
        if day != current_day:
            current_day = day
            daily_hours = random.uniform(6, 15)

        data["machine_hours_today"][i] = daily_hours
        cumulative_hours += 1
        data["total_machine_hours"][i] = cumulative_hours

    # Tool usage simulation
    tool_usage = 0
    for i in range(n_samples):
        if i > 0:
            if tool_usage > 4000:
                tool_usage = 0
            else:
                tool_usage += random.uniform(10, 20)
        data["tool_usage_min"][i] = tool_usage

    return pd.DataFrame(data)

# Generate base normal data
df = generate_normal_data(n_samples)

# Anomaly definitions
anomaly_types = {
    "tool_wear": {
        "vibration_rms": 1.5,
        "cutting_force_N": 1.3,
        "acoustic_level_dB": 1.2,
        "tool_usage_min": 1.0,
        "severity_impact": 0.7,
        "progression_rate": 1.2
    },
    "tool_break": {
        "vibration_rms": 2.5,
        "cutting_force_N": 0.7,
        "acoustic_level_dB": 1.5,
        "spindle_current_A": 1.3,
        "severity_impact": 0.9,
        "progression_rate": 1.8
    },
    "motor_overheating": {
        "motor_temp_C": 1.4,
        "power_consumption_W": 1.2,
        "spindle_current_A": 1.15,
        "severity_impact": 0.8,
        "progression_rate": 1.0
    },
    "coolant_failure": {
        "coolant_temp_C": 1.5,
        "motor_temp_C": 1.2,
        "severity_impact": 0.85,
        "progression_rate": 1.5
    },
    "power_supply_issue": {
        "power_consumption_W": 1.3,
        "spindle_current_A": 0.85,
        "rpm": 0.9,
        "severity_impact": 0.75,
        "progression_rate": 0.8
    }
}

# Generate health and maintenance patterns
def generate_health_and_maintenance(df):
    df['machine_health_score'] = np.zeros(len(df))
    df['days_to_maintenance'] = np.zeros(len(df))
    df['is_anomaly'] = np.zeros(len(df))
    df['anomaly_type'] = 'normal'
    df['anomaly_severity'] = np.zeros(len(df))

    current_health = 100.0
    health_decay_per_hour = 0.02

    maintenance_points = []
    for i in range(1, 4):
        day = i * 30 + random.randint(-5, 5)
        hour = random.randint(0, 23)
        maintenance_points.append(day * 24 + hour)

    for i in range(len(df)):
        if i > 0:
            usage_factor = 1.0 + (df.loc[i, 'total_machine_hours'] - df.loc[i-1, 'total_machine_hours']) / 1000
            current_health -= health_decay_per_hour * usage_factor
            current_health = max(20, current_health)

        df.loc[i, 'machine_health_score'] = current_health

        if current_health > 80:
            days_to_maint = 30
        elif current_health > 60:
            days_to_maint = 20
        elif current_health > 40:
            days_to_maint = 10
        else:
            days_to_maint = max(0, int(current_health / 10))

        df.loc[i, 'days_to_maintenance'] = days_to_maint

        if i in maintenance_points:
            current_health = 100.0
            df.loc[i, 'days_to_maintenance'] = 30

    df['machine_health_score'] += np.random.normal(0, 1, len(df))
    df['machine_health_score'] = df['machine_health_score'].clip(0, 100)

    return df

df = generate_health_and_maintenance(df)

# Introduce anomalies (guaranteed at least one)
def introduce_anomalies(df, anomaly_percentage=0.15):
    total_hours = len(df)
    total_anomaly_hours = int(total_hours * anomaly_percentage)

    if total_anomaly_hours == 0:
        total_anomaly_hours = 12

    sequences = []
    remaining_hours = total_anomaly_hours

    while remaining_hours > 0:
        seq_length = min(random.randint(6, 48), remaining_hours)
        sequences.append(seq_length)
        remaining_hours -= seq_length

    if len(sequences) == 0:
        sequences = [12]

    random.shuffle(sequences)

    for seq_length in sequences:
        anomaly_type = random.choice(list(anomaly_types.keys()))
        anomaly_config = anomaly_types[anomaly_type]

        start_pos = random.randint(48, len(df) - seq_length - 48)
        while any(df.iloc[max(0, start_pos-48):min(len(df), start_pos+seq_length+48)]['is_anomaly'] > 0):
            start_pos = random.randint(48, len(df) - seq_length - 48)

        progression_rate = anomaly_config["progression_rate"]
        severity_impact = anomaly_config["severity_impact"]

        for i in range(seq_length):
            pos = start_pos + i
            severity = max(0.1, min(1.0, (i / seq_length) * progression_rate + np.random.normal(0, 0.05)))
            df.loc[pos, 'is_anomaly'] = 1
            df.loc[pos, 'anomaly_type'] = anomaly_type
            df.loc[pos, 'anomaly_severity'] = severity

            for metric, multiplier in anomaly_config.items():
                if metric in df.columns and metric not in ['severity_impact', 'progression_rate']:
                    effect = 1.0 + (multiplier - 1.0) * severity
                    df.loc[pos, metric] = df.loc[pos, metric] * effect

            health_impact = -50 * severity * severity_impact
            df.loc[pos, 'machine_health_score'] = max(0, min(100, df.loc[pos, 'machine_health_score'] + health_impact))

    return df

df = introduce_anomalies(df)

# Additional features
df["vibration_trend"] = df["vibration_rms"].rolling(window=24, min_periods=1).mean()
df["motor_temp_trend"] = df["motor_temp_C"].rolling(window=24, min_periods=1).mean()
df["power_efficiency"] = df["rpm"] / df["power_consumption_W"] * 1000
df["tool_wear_rate"] = df["tool_usage_min"].diff().fillna(0)
df["vibration_std_24h"] = df["vibration_rms"].rolling(window=24, min_periods=1).std()
df["temp_rate_change"] = df["motor_temp_C"].diff().fillna(0)
df["current_stability"] = df["spindle_current_A"].rolling(window=12, min_periods=1).std()

# Save dataset
df.to_csv("cnc_machine_data_improved.csv", index=False)

# Visualization
plt.figure(figsize=(15, 12))
plt.subplot(3, 1, 1)
plt.plot(df['timestamp'], df['machine_health_score'])
plt.title('Machine Health Score Over Time')
plt.ylabel('Health Score')
plt.grid(True)

plt.subplot(3, 1, 2)
plt.plot(df['timestamp'], df['days_to_maintenance'])
plt.title('Days to Maintenance Over Time')
plt.ylabel('Days')
plt.grid(True)

plt.subplot(3, 1, 3)
for anomaly_type in df['anomaly_type'].unique():
    if anomaly_type != 'normal':
        mask = df['anomaly_type'] == anomaly_type
        plt.scatter(df.loc[mask, 'timestamp'], df.loc[mask, 'anomaly_severity'],
                    label=anomaly_type, alpha=0.7)

plt.title('Anomaly Occurrences and Severity')
plt.ylabel('Severity')
plt.legend()
plt.tight_layout()
plt.savefig('data_visualization.png')

print(f"Generated {len(df)} data points with {df['is_anomaly'].sum()} anomaly points")
print(f"Dataset saved to cnc_machine_data_improved.csv")
print(f"Visualizations saved to data_visualization.png")

print("\nDataset Summary:")
print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"Anomaly types: {df[df['is_anomaly']==1]['anomaly_type'].unique()}")
print(f"Health score range: {df['machine_health_score'].min():.1f} to {df['machine_health_score'].max():.1f}")
print(f"Days to maintenance range: {df['days_to_maintenance'].min():.1f} to {df['days_to_maintenance'].max():.1f}")

health_maint_corr = df['machine_health_score'].corr(df['days_to_maintenance'])
print(f"\nCorrelation between health score and days to maintenance: {health_maint_corr:.4f}")

anomaly_percentage = df['is_anomaly'].mean() * 100
print(f"Percentage of anomalies in dataset: {anomaly_percentage:.2f}%")

anomaly_counts = df[df['is_anomaly']==1]['anomaly_type'].value_counts()
print("\nAnomaly distribution:")
for anomaly_type, count in anomaly_counts.items():
    print(f"- {anomaly_type}: {count} instances ({count/df['is_anomaly'].sum()*100:.1f}%)")
