import warnings

warnings.filterwarnings('ignore')

from sklearn.metrics import fbeta_score
import pickle
from sklearn.metrics import f1_score
from collections import OrderedDict
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import flwr as fl
import itertools as it
from flwr.common import Metrics
from datetime import datetime, timedelta
from sklearn.metrics import classification_report
from torch.utils.data import DataLoader, Dataset
import random
import os
#from .aggregate import aggregate_median
# flower imports for custom strategy

from typing import Callable, Dict, List, Optional, Tuple, Union
from flwr.common import (
    EvaluateIns,
    EvaluateRes,
    FitIns,
    FitRes,
    MetricsAggregationFn,
    NDArrays,
    Parameters,
    Scalar,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import aggregate, aggregate_median, weighted_loss_avg, aggregate_krum, aggregate_trimmed_avg, aggregate_bulyan

DEVICE = torch.device("cpu")  # Try "cuda" to train on GPU
print(
    f"Training on {DEVICE} using PyTorch {torch.__version__} and Flower {fl.__version__}"
)

NUM_CLIENTS = 10
BATCH_SIZE = 32
time_frequency = 60 * 24
chunk_size = 10

seed = 42
torch.manual_seed(seed)
np.random.seed(seed)
random.seed(seed)

def datetime_range(start, end, delta):
    current = start
    while current <= end:
        yield current
        current += delta


def moving_window(x, length, step=1):
    streams = it.tee(x, length)
    return zip(*[it.islice(stream, i, None, step) for stream, i in zip(streams, it.count(step=step))])
#
# def choose_target_generate_fllist(sheroaks_crime):
#     crime_type = 8
#     start_time_so = '1/1/2015'
#     end_time_so = '12/31/2015'
#     format_string = '%m/%d/%Y'
#     start_time_so = datetime.strptime(start_time_so, format_string)
#     end_time_so = datetime.strptime(end_time_so, format_string)
#     time_list_so = [dt.strftime('%m/%d/%Y') for dt in
#                     datetime_range(start_time_so, end_time_so, timedelta(minutes=time_frequency))]
#
#     x_ = list(moving_window(time_list_so, chunk_size))
#
#     # Ensure date column in DataFrame is in datetime format
#     sheroaks_crime['date'] = pd.to_datetime(sheroaks_crime['date'], format='%m/%d/%Y', errors='coerce')
#
#     final_list_so = []
#     label_list_so = []
#     for i in range(len(x_)):
#         feature_time_frame = x_[i][:chunk_size - 1]
#         feature_list = []
#         for index_fea in range(len(feature_time_frame) - 1):
#             start_so = feature_time_frame[index_fea]
#             end_so = feature_time_frame[index_fea + 1]
#             df_so_middle = sheroaks_crime.loc[
#                 (sheroaks_crime['date'] >= start_so) & (sheroaks_crime['date'] < end_so)]
#             crime_record = np.zeros(crime_type)
#             for index, row in df_so_middle.iterrows():
#                 crime_record[int(row["crime_type_id"])] = 1
#             feature_list.append(crime_record)
#         final_list_so.append(feature_list)
#
#
#         label_time_frame = x_[i][chunk_size - 2:]
#         label_time_slots = sheroaks_crime.loc[
#             (sheroaks_crime['date'] >= label_time_frame[0]) & (sheroaks_crime['date'] < label_time_frame[1])]
#         crime_record = np.zeros(crime_type)
#         for index_label, row_label in label_time_slots.iterrows():
#             crime_record[int(row_label["crime_type_id"])] = 1
#         label_list_so.append(crime_record)
#
#     #print("the shape of feature list is {}, and the shape of label list is {} ".format(np.shape(final_list_so), np.shape(label_list_so)))
#     return final_list_so, label_list_so

def choose_target_generate_fllist(sheroaks_crime):
    crime_type = 8
    start_time_so = '2018-01-01'
    end_time_so = '2018-12-31'
    format_string = '%Y-%m-%d'
    start_time_so = datetime.strptime(start_time_so, format_string)
    end_time_so = datetime.strptime(end_time_so, format_string)
    time_list_so = [dt.strftime('%Y-%m-%d') for dt in
                    datetime_range(start_time_so, end_time_so, timedelta(minutes=time_frequency))]
    x_ = list(moving_window(time_list_so, chunk_size))
    final_list_so = []
    label_list_so = []
    for i in range(len(x_)):
        feature_time_frame = x_[i][:chunk_size - 1]
        feature_list = []
        for index_fea in range(len(feature_time_frame) - 1):
            start_so = feature_time_frame[index_fea]
            end_so = feature_time_frame[index_fea + 1]
            df_so_middle = sheroaks_crime.loc[
                (sheroaks_crime['date_occ'] >= start_so) & (sheroaks_crime['date_occ'] < end_so)]
            crime_record = np.zeros(crime_type)
            for index, row in df_so_middle.iterrows():
                crime_record[int(row["crime_type_id"])] = 1
            feature_list.append(crime_record)
        final_list_so.append(feature_list)

        label_time_frame = x_[i][chunk_size - 2:]
        label_time_slots = sheroaks_crime.loc[
            (sheroaks_crime['date_occ'] >= label_time_frame[0]) & (sheroaks_crime['date_occ'] < label_time_frame[1])]
        crime_record = np.zeros(crime_type)
        for index_label, row_label in label_time_slots.iterrows():
            crime_record[int(row_label["crime_type_id"])] = 1
        label_list_so.append(crime_record)

    # print("the shape of feature list is {}, and the shape of label list is {} ".format(np.shape(final_list_so), np.shape(label_list_so)))
    return final_list_so, label_list_so

class CustomDataset(Dataset):
    def __init__(self, features, labels):
        self.features = features
        self.labels = labels

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        feature = torch.tensor(self.features[idx], dtype=torch.float32)
        label = torch.tensor(self.labels[idx], dtype=torch.float32)
        return feature, label


def load_datasets():
    PATH = 'C:\\Users\\cbhum\\OneDrive\\Documents\\Datasets\\crime\\'
    df = pd.read_csv(PATH + 'processed_crime.csv')
    #print(df.head())

    # Create train/val for each partition and wrap it into DataLoader
    trainloaders = []
    valloaders = []
    testloaders = []
    globaltestloaders = []

    # Group the DataFrame by 'neighborhood_id' and calculate the size of each group
    group_partition = df.groupby('neighborhood_id')

    x_global_test = []
    target_global_test = []

    for partition_id, partition_df in group_partition:
      if partition_id in [58, 20, 75, 53, 93, 81, 68, 45, 13, 108]:
        feature, label = choose_target_generate_fllist(partition_df)
        num_samples = len(feature)

        # Calculate the sizes for training, validation, test, and global test sets
        num_train = round(num_samples * 0.5417)  # 65% for training
        num_val = round(num_samples * 0.0417)  # 5% for validation
        num_test = round(num_samples * 0.0833)  # 10% for testing

        # Training, Validation, and Test set
        x_train, target_train = feature[:num_train], label[:num_train]
        x_val, target_val = feature[num_train:num_train + num_val], label[num_train:num_train + num_val]
        x_test, target_test = feature[num_train + num_val : num_train + num_val + num_test], label[num_train + num_val : num_train + num_val + num_test ]
        # Append data for partitions to the global test set
        x_global_test.extend(x_test)
        target_global_test.extend(target_test)
        train_dataset = CustomDataset(x_train, target_train)
        val_dataset = CustomDataset(x_val, target_val)
        test_dataset = CustomDataset(x_test, target_test)

        trainloaders.append(DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=False))
        valloaders.append(DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False))
        testloaders.append(DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False))

    #Global Test set
    global_test_dataset = CustomDataset(x_global_test, target_global_test)
    globaltestloaders.append(DataLoader(global_test_dataset, batch_size=BATCH_SIZE, shuffle=False))

    return trainloaders, valloaders, testloaders, globaltestloaders

# load datasets
trainloaders, valloaders, testloaders, globaltestloaders = load_datasets()


class TCNBlock(nn.Module):
    """ A single TCN residual block """
    def __init__(self, in_channels, out_channels, kernel_size=3, dilation=1):
        super(TCNBlock, self).__init__()
        padding = (kernel_size - 1) * dilation // 2  # Keep output size same
        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size, padding=padding, dilation=dilation)
        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size, padding=padding, dilation=dilation)
        self.relu = nn.ReLU()
        self.residual = nn.Conv1d(in_channels, out_channels, kernel_size=1) if in_channels != out_channels else nn.Identity()

    def forward(self, x):
        res = self.residual(x)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        return x + res  # Residual connection

class Net(nn.Module):
    def __init__(self, num_inputs=8, hidden_units=16, num_layers=3, kernel_size=3):
        super().__init__()
        self.num_inputs = num_inputs
        self.hidden_units = hidden_units
        # TCN Layers
        layers = []
        for i in range(num_layers):
            in_channels = num_inputs if i == 0 else hidden_units
            layers.append(TCNBlock(in_channels, hidden_units, kernel_size, dilation=2**i))  # Increasing dilation
        self.tcn = nn.Sequential(*layers)
        # Fully connected layers for outputs
        self.linear = nn.Linear(hidden_units, 8)  # Zero-inflation probability
        # Activation functions
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x = x.permute(0, 2, 1)  # Change to (batch, channels, sequence_length) for TCN
        tcn_out = self.tcn(x)
        tcn_out = tcn_out[:, :, -1]  # Take last time step output
        out = self.sigmoid(self.linear(tcn_out))
        return out


# class Net(nn.Module):
#     def __init__(self, num_inputs=8, hidden_units=16):
#         super().__init__()
#         self.num_inputs = num_inputs  # this is the number of features
#         self.hidden_units = hidden_units
#         self.num_layers = 1
#         # print("client model Initialization starting")
#
#         self.lstm = nn.LSTM(
#             input_size=num_inputs,
#             hidden_size=hidden_units,
#             batch_first=True,
#             num_layers=self.num_layers
#         )
#
#         self.linear = nn.Linear(in_features=self.hidden_units, out_features=8)
#         self.sigmoid = nn.Sigmoid()
#         self.relu = nn.ReLU()
#         # print("client model Initialization Complete")
#
#     def forward(self, x):
#         batch_size = x.shape[0]
#         h0 = torch.zeros(self.num_layers, batch_size, self.hidden_units)
#         c0 = torch.zeros(self.num_layers, batch_size, self.hidden_units)
#
#         _, (hn, _) = self.lstm(x, (h0, c0))
#
#         out = self.relu(hn[0])
#         out = self.linear(out)
#         out = self.sigmoid(out)
#         return out


# class Net(nn.Module):
#     def __init__(self, num_inputs=8, hidden_units=16):
#         super().__init__()
#         self.num_inputs = num_inputs
#         self.hidden_units = hidden_units
#         self.num_layers = 1
#
#         self.lstm = nn.LSTM(
#             input_size=num_inputs,
#             hidden_size=hidden_units,
#             batch_first=True,
#             num_layers=self.num_layers
#         )
#
#         # Linear layers for outputs
#         self.fc_zero = nn.Linear(hidden_units, 8)  # Zero-inflation probability
#         self.fc_nb_mean = nn.Linear(hidden_units, 8)  # Negative binomial mean
#         self.fc_nb_disp = nn.Linear(hidden_units, 8)  # Negative binomial dispersion (log scale)
#
#         # Activation functions
#         self.sigmoid = nn.Sigmoid()
#         self.softplus = nn.Softplus()  # Ensures non-negative values for dispersion
#         #self.class_weights = nn.Parameter(torch.ones(8))
#
#     def forward(self, x):
#         batch_size = x.shape[0]
#         h0 = torch.zeros(self.num_layers, batch_size, self.hidden_units)
#         c0 = torch.zeros(self.num_layers, batch_size, self.hidden_units)
#
#         _, (hn, _) = self.lstm(x, (h0, c0))
#
#         out = hn[0]  # First dim of hn is num_layers, which is 1
#
#         zero_prob = self.sigmoid(self.fc_zero(out))  # Zero-inflation probability
#         nb_mean = torch.exp(self.fc_nb_mean(out))  # NB mean (ensured positive)
#         nb_disp = self.softplus(self.fc_nb_disp(out))  # NB dispersion (positive via softplus)
#
#         return zero_prob, nb_mean, nb_disp

def zimnb_loss(zero_prob, nb_mean, nb_disp, targets):
    eps = 1e-10  # Small value to prevent log(0)

    # Binary cross-entropy for zero-inflation part
    zero_loss = targets.eq(0).float() * torch.log(zero_prob + eps)

    # Negative binomial log likelihood for non-zero counts
    targets_nonzero = targets.gt(0).float()
    log_factorial = torch.lgamma(targets + 1)

    # NB likelihood (log NB PMF)
    nb_loss = targets_nonzero * (
        torch.lgamma(targets + nb_disp) - torch.lgamma(nb_disp)
        - log_factorial + nb_disp * (torch.log(nb_disp) - torch.log(nb_disp + nb_mean))
        + targets * (torch.log(nb_mean) - torch.log(nb_disp + nb_mean))
    )

    # Total loss (negative log likelihood)
    total_loss = -torch.mean(zero_loss + nb_loss)

    return total_loss

def train(net, trainloader, learning_rate, epochs: int):
    """Train the network on the training set."""
    all_predictions, all_labels = [], []
    criterion = torch.nn.BCELoss()
    optimizer = torch.optim.Adam(list(net.parameters()) + list(criterion.parameters()), lr=learning_rate, weight_decay=1e-4)
    correct_train, total_train, epoch_loss_train = 0, 0, 0.0
    net.train()
    for epoch in range(epochs):
        correct, total, epoch_loss = 0, 0, 0.0
        for batch in trainloader:
            x, labels = batch[0], batch[1]
            optimizer.zero_grad()
            preds = net(x)
            #loss = zimnb_loss(zero_prob, mu, dispersion, labels)
            loss = criterion(preds, labels)
            loss.backward()
            optimizer.step()
            epoch_loss_train += loss.item()
            total_train += labels.size(0)
            predicted_labels = (preds > 0.5).float()
            all_predictions.extend(predicted_labels.tolist())
            all_labels.extend(labels.tolist())
            # Compute accuracy for each sample and each label
            correct_train += ((predicted_labels == labels).float().sum(dim=1) == labels.size(1)).sum().item()

            # if batch % 10 == 0:
            #     loss, current = loss.item(), batch * len(x)
            #     print(f"Inside batch loss: {loss:>7f}  [{current:>5d}/{size:>5d}]")

        epoch_loss_train /= len(trainloader.dataset)
        #epoch_acc = correct_train / total_train
        epoch_loss_train /= len(trainloader)
        macro_f1 = f1_score(all_labels, all_predictions, average='macro')
        micro_f1 = f1_score(all_labels, all_predictions, average='micro')
        print(f"Epoch {epoch + 1}: train loss {epoch_loss}, macro F1 {macro_f1}, micro F1 {micro_f1}")
        return epoch_loss_train, micro_f1, macro_f1



def val(net, testloader):
    """Evaluate the network on the entire test set."""
    all_predictions, all_labels, macro, micro = [], [], [], []
    criterion = torch.nn.BCELoss()
    correct, total, loss = 0, 0, 0.0
    net.eval()
    with torch.no_grad():
        for batch in testloader:
            features, labels = batch[0], batch[1]
            preds = net(features)
            #loss += zimnb_loss(zero_prob, mu, dispersion, labels).item()
            loss += criterion(preds, labels).item()
            #_, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            predicted_labels = (preds > 0.5).float()
            all_predictions.extend(predicted_labels.tolist())
            all_labels.extend(labels.tolist())
            # Compute accuracy for each sample and each label
            correct += ((predicted_labels == labels).float().sum(dim=1) == labels.size(1)).sum().item()
    loss /= len(testloader.dataset)
    accuracy = correct / total
    macro_f1 = f1_score(all_labels, all_predictions, average='macro')
    micro_f1 = f1_score(all_labels, all_predictions, average='micro')
    return loss, accuracy, micro_f1, macro_f1


def test(net, testloader):
    """Evaluate the network on the entire test set."""
    all_predictions, all_labels, macro, micro = [], [], [], []
    criterion = torch.nn.BCELoss()
    correct, total, loss = 0, 0, 0.0
    net.eval()
    with torch.no_grad():
        for batch in testloader:
            features, labels = batch[0], batch[1]
            preds = net(features)
            #loss += zimnb_loss(zero_prob, mu, dispersion, labels).item()
            loss += criterion(preds, labels)
            #_, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            predicted_labels = (preds > 0.5).float()
            all_predictions.extend(predicted_labels.tolist())
            all_labels.extend(labels.tolist())
            # Compute accuracy for each sample and each label
            correct += ((predicted_labels == labels).float().sum(dim=1) == labels.size(1)).sum().item()
    loss /= len(testloader.dataset)
    accuracy = correct / total
    macro_f1 = f1_score(all_labels, all_predictions, average='macro')
    micro_f1 = f1_score(all_labels, all_predictions, average='micro')
    class_report = classification_report(all_labels, all_predictions)
    return loss, accuracy, micro_f1, macro_f1, class_report


def set_parameters(net, parameters: List[np.ndarray]):
    params_dict = zip(net.state_dict().keys(), parameters)
    state_dict = OrderedDict({k: torch.Tensor(v) for k, v in params_dict})
    net.load_state_dict(state_dict, strict=True)


def get_parameters(net) -> List[np.ndarray]:
    return [val.cpu().numpy() for _, val in net.state_dict().items()]


class FlowerNumPyClient(fl.client.NumPyClient):
    def __init__(self, cid, net, trainloader, valloader, testloader):
        self.cid = cid
        self.net = net
        self.trainloader = trainloader
        self.valloader = valloader
        self.testloader = testloader

    def get_parameters(self, config):
        print(f"[Client {self.cid}] get_parameters")
        return get_parameters(self.net)

    def fit(self, parameters, config):
        print(f"[Client {self.cid}] fit, config: {config}")
        set_parameters(self.net, parameters)
        #if self.cid in [0, 3, 10, 15]:
        learning_r = config["lr"]
        server_round = config["round"]
        # file writing
        # os.makedirs("../store_results", exist_ok=True)
        # file_path_1 = os.path.join("../store_results", f"fit_before_client_results.txt")
        # test_loss, test_accuracy, test_micro, test_macro, class_report = test(self.net, self.testloader)
        # with open(file_path_1, "a") as file:
        #     file.write(f"{self.cid},{server_round},{test_loss},{test_micro}, {test_macro}\n")
        # if server_round == 50:
        #     file_path_3 = os.path.join("../store_results", f"before_class_wise_report.txt")
        #     with open(file_path_3, "a") as file:
        #         file.write(f"{server_round},{self.cid},{class_report}\n")

        train_loss, train_micro, train_macro = train(self.net, self.trainloader, learning_r, epochs=5)
        val_loss, val_accuracy, val_micro, val_macro = val(self.net, self.valloader)
        print(f" fit Val loss {val_loss}, Test accuracy {val_accuracy}, micro F1 {val_micro}, macro F1 {val_macro}")
        # test_loss, test_accuracy, test_micro, test_macro, class_report = test(self.net, self.testloader)
        # print(f" fit test loss {test_loss}, Test accuracy {test_accuracy}, micro F1 {test_micro}, macro F1 {test_macro}")
        # # Logging.info(f"client {self.cid}: loss: {test_loss}, micro: {test_micro}, macro: {test_macro}")
        # file_path_2 = os.path.join("../store_results", f"fit_after_client_results.txt")
        # # File Writing
        # with open(file_path_2, "a") as file:
        #     file.write(f"{self.cid},{server_round},{test_loss},{test_micro}, {test_macro}\n")
        #
        # if server_round == 50:
        #      file_path_4 = os.path.join("../store_results", f"after_class_wise_report.txt")
        #      with open(file_path_4, "a") as file:
        #          file.write(f"{server_round},{self.cid},{class_report}\n")

        return get_parameters(self.net), len(self.trainloader), {"loss": float(train_loss), "micro": float(train_micro),
                                                                 "macro": float(train_macro)}

    def evaluate(self, parameters, config):
        print(f"[Client {self.cid}] evaluate, config: {config}")
        set_parameters(self.net, parameters)
        server_round = config["round"]
        loss, accuracy, micro, macro, class_report = test(self.net, self.testloader)
        print(f" Evaluate Test loss {loss}, Test accuracy {accuracy}, micro F1 {micro}, macro F1 {macro}")
        if server_round == 50:
            file_path_class = "../store_results/class_wise_report.txt"
            with open(file_path_class, "a") as file:
                file.write(f"{self.cid},{class_report}\n")

            file_path = "../store_results/evaluate_client_results.txt"
            # Open the file for writing
            with open(file_path, "a") as file:
                file.write(f"{self.cid},{loss},{micro},{macro}\n")


        return float(loss), len(self.testloader), {"micro": float(micro), "macro": float(macro)}


def numpyclient_fn(cid) -> FlowerNumPyClient:
    net = Net().to(DEVICE)
    trainloader = trainloaders[int(cid)]
    valloader = valloaders[int(cid)]
    testloader = testloaders[int(cid)]
    return FlowerNumPyClient(cid, net, trainloader, valloader, testloader)


def weighted_average(metrics: List[Tuple[int, Metrics]]) -> Metrics:
    # Multiply accuracy of each client by number of examples used
    micros = [num_examples * m["micro"] for num_examples, m in metrics]
    macros = [num_examples * m["macro"] for num_examples, m in metrics]
    examples = [num_examples for num_examples, _ in metrics]

    # Aggregate and return custom metric (weighted average)
    return {"micro": sum(micros) / sum(examples), "macro": sum(macros) / sum(examples)}



params = get_parameters(Net())

# centralized evaluation
def evaluate(
        server_round: int,
        parameters: fl.common.NDArrays,
        config: dict[str, fl.common.Scalar], ):
    net = Net().to(DEVICE)
    set_parameters(net, parameters)  # Update model with the latest parameters
    losses, accuracys, micros, macros = [], [], [], []
    for batch_idx, globaltestloader in enumerate(globaltestloaders):
        loss, accuracy, micro, macro, class_report = test(net, globaltestloader)
        losses.append(loss)
        accuracys.append(accuracy)
        micros.append(micro)
        macros.append(macro)

    loss = sum(losses) / len(losses)
    accuracy = sum(accuracys) / len(accuracys)
    micro = sum(micros) / len(micros)
    macro = sum(macros) / len(macros)

    # print(f"Server-side evaluation: round {server_round} loss {loss}, accuracy {accuracy}, micro {micro}, macro {macro}")
    # file_path = "../store_results/evaluate_server_bulyan_gamma.txt"
    # # Open the file for writing
    # with open(file_path, "a") as file:
    #     file.write(f"{server_round},{loss},{micro},{macro}\n")
    return loss, {"micro": micro, "macro": macro}

class FedCrime(fl.server.strategy.Strategy):
    def __init__(
        self,
        fraction_fit: float = 1.0,
        fraction_evaluate: float = 1.0,
        min_fit_clients: int = 10,
        min_evaluate_clients: int = 10,
        min_available_clients: int = 10,
        #initial_parameters: Optional[Parameters] = None,
        evaluate_fn=evaluate,  # Pass the evaluation function
        evaluate_metrics_aggregation_fn=weighted_average,
    ) -> None:
        super().__init__()
        self.fraction_fit = fraction_fit
        self.fraction_evaluate = fraction_evaluate
        self.min_fit_clients = min_fit_clients
        self.min_evaluate_clients = min_evaluate_clients
        self.min_available_clients = min_available_clients
        #self.initialize_parameters = initial_parameters
        self.evaluate_fn = evaluate_fn
        self.evaluate_metrics_aggregation_fn = evaluate_metrics_aggregation_fn

    def __repr__(self) -> str:
        return "FedCrime"

    def initialize_parameters(
        self, client_manager: ClientManager
    ) -> Optional[Parameters]:
        """Initialize global model parameters."""
        net = Net()
        ndarrays = get_parameters(net)
        return fl.common.ndarrays_to_parameters(ndarrays)

    def configure_fit(
        self, server_round: int, parameters: Parameters, client_manager: ClientManager
    ) -> List[Tuple[ClientProxy, FitIns]]:
        """Configure the next round of training."""

        # Sample clients
        sample_size, min_num_clients = self.num_fit_clients(
            client_manager.num_available()
        )
        clients = client_manager.sample(
            num_clients=sample_size, min_num_clients=min_num_clients
        )
        # Create custom configs
        dense_config = {"lr": 0.001}
        moderate_config = {"lr": 0.01,"round":server_round}
        sparse_config = {"lr": 0.1}

        # Create custom configs
        config = {}
        fit_configurations = []
        for idx, client in enumerate (clients):
            #print("I am in config fit",idx)
            #if idx in [39, 6, 50]:
            fit_configurations.append((client, FitIns(parameters, moderate_config)))
            # elif idx in [18, 29, 81]:
            #     fit_configurations.append((client, FitIns(parameters, moderate_config)))
            # elif idx in [102, 80, 51, 92, 110]:
            #     fit_configurations.append((client, FitIns(parameters, moderate_config)))

        return fit_configurations

    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple[ClientProxy, FitRes]],
        failures: List[Union[Tuple[ClientProxy, FitRes], BaseException]],
    ) -> Tuple[Optional[Parameters], Dict[str, Scalar]]:
        """Aggregate fit results using weighted average."""
        weights_results = [
            (parameters_to_ndarrays(fit_res.parameters), fit_res.num_examples)
            for _, fit_res in results
        ]

        num_malicious_clients = 1
        #num_clients_to_keep = 6 # aggregate_krum(weights_results, num_malicious_clients, num_clients_to_keep)
        #ndarrays_to_parameters(aggregate_trimmed_avg(weights_results, proportiontocut = 0.4))
        krum_callable = aggregate_krum
        self.aggregation_rule_kwargs = {"to_keep": 0}
        parameters_aggregated = ndarrays_to_parameters(aggregate_bulyan(weights_results, num_malicious_clients, krum_callable, **self.aggregation_rule_kwargs))

        agg_macro, agg_micro = [], []
        for client, fit_res in results:
            metrics = fit_res.metrics
            agg_macro.append(metrics['macro'])
            agg_micro.append(metrics['micro'])

        macro = sum(agg_macro)/len(agg_macro)
        micro = sum(agg_micro) / len(agg_micro)

        #print("Aggregated macro and micro", macro, micro)

        metrics_aggregated = {'macro': macro, 'micro': micro }
        return parameters_aggregated, metrics_aggregated

    def configure_evaluate(
        self, server_round: int, parameters: Parameters, client_manager: ClientManager
    ) -> List[Tuple[ClientProxy, EvaluateIns]]:
        """Configure the next round of evaluation."""
        if self.fraction_evaluate == 0.0:
            return []
        config = {"round" : server_round}
        evaluate_ins = EvaluateIns(parameters, config)

        # Sample clients
        sample_size, min_num_clients = self.num_evaluation_clients(
            client_manager.num_available()
        )
        clients = client_manager.sample(
            num_clients=sample_size, min_num_clients=min_num_clients
        )
        # Return client/config pairs
        return [(client, evaluate_ins) for client in clients]

    def aggregate_evaluate(
        self,
        server_round: int,
        results: List[Tuple[ClientProxy, EvaluateRes]],
        failures: List[Union[Tuple[ClientProxy, EvaluateRes], BaseException]],
    ) -> Tuple[Optional[float], Dict[str, Scalar]]:
        """Aggregate evaluation losses using weighted average."""

        if not results:
            return None, {}

        loss_aggregated = weighted_loss_avg(
            [
                (evaluate_res.num_examples, evaluate_res.loss)
                for _, evaluate_res in results
            ]
        )
        # Iterate over results
        agg_macro, agg_micro = [], []
        for client, eval_res in results:
            metrics = eval_res.metrics
            agg_macro.append(metrics['macro'])
            agg_micro.append(metrics['micro'])

        macro = sum(agg_macro)/len(agg_macro)
        micro = sum(agg_micro) / len(agg_micro)

        #print("Aggregated macro and micro", macro, micro)

        metrics_aggregated = {'macro': macro, 'micro': micro }
        return loss_aggregated, metrics_aggregated

    def evaluate(
            self, server_round: int, parameters: Parameters
    ) -> Optional[Tuple[float, Dict[str, Scalar]]]:
        """Evaluate model parameters using an evaluation function."""
        if self.evaluate_fn is None:
            return None
        parameters_ndarrays = parameters_to_ndarrays(parameters)
        eval_res = self.evaluate_fn(server_round, parameters_ndarrays, {})
        if eval_res is None:
            return None
        loss, metrics = eval_res
        return loss, metrics
    def num_fit_clients(self, num_available_clients: int) -> Tuple[int, int]:
        """Return sample size and required number of clients."""
        num_clients = int(num_available_clients * self.fraction_fit)
        return max(num_clients, self.min_fit_clients), self.min_available_clients

    def num_evaluation_clients(self, num_available_clients: int) -> Tuple[int, int]:
        """Use a fraction of available clients for evaluation."""
        num_clients = int(num_available_clients * self.fraction_evaluate)
        return max(num_clients, self.min_evaluate_clients), self.min_available_clients



# client will be allocated 1x CPU and 0x GPUs
client_resources = {"num_cpus": 1, "num_gpus": 0.0}

# Start simulation
history = fl.simulation.start_simulation(
    client_fn=numpyclient_fn,
    num_clients=NUM_CLIENTS,
    config=fl.server.ServerConfig(num_rounds=50),
    strategy= FedCrime(),
    client_resources=client_resources,
)

# Save object to file
with open('../../data.pickle', 'wb') as f:
    pickle.dump(history, f)

