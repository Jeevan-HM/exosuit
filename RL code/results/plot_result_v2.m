clc; clear; close all;

% train_data = readmatrix('../gait_data_2control.csv');
% valid_data = readmatrix('valid1.csv');
% train_acc = readmatrix('training1.csv');

train_data = readmatrix('../gait_data_realtime.csv');
valid_data = readmatrix('valid_realtime.csv');
train_acc = readmatrix('training_realtime.csv');

%Truncate Training data to match validation data size.
train_data = train_data(1:length(valid_data), :);
disp('NOTE: Train data was truncated.')

i = 1:height(train_data);
%%plot training and valid data action 1
figure(1); clf;
stem(i-0.1,(((train_data(:,5)+1)*(1.736-0.08))/2+0.08),'LineWidth',3)
hold on
stem(i+0.1,(((valid_data(:,2)+1)*(1.736-0.08))/2+0.08),'LineWidth',3)
grid on
legend('Huristic controller U1','Offline RL controller U1')
set(gca,'fontsize',18)
xlabel('state number')
ylabel('U1 timing value (sec)')


%%plot training and valid data action 2
figure(2); clf;
stem(i-0.1,(((train_data(:,6)+1)*(0.95-0.04))/2+0.04),'LineWidth',3)
hold on
stem(i+0.1,(((valid_data(:,3)+1)*(0.95-0.04))/2+0.04),'LineWidth',3)
grid on
legend('Huristic controller U2','Offline RL controller U2')
set(gca,'fontsize',18)
xlabel('state number')
ylabel('U2 timing value (sec)')

i = 1:height(train_acc);
figure(3); clf;
plot(i,train_acc(:,2),'LineWidth',3)
legend('Training Cost')
set(gca,'fontsize',18)
xlabel('Training Iteration number')
ylabel('Cost')