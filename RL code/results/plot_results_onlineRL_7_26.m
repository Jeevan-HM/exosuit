%% Plots results of online RL 

clc; clear;

filename = 'online_10_10_trial2.csv'



data = readmatrix(filename);

%Delete EMG outlier
if string(filename) == "dhdp_online_10_10_trial1.csv"
    data(26,:) = [];
elseif string(filename) == "dhdp_online_6_30_trial2.csv"
    data(30,:) = [];
end

cost = data(:,2);
t1_error = data(:,3);
d1_error = data(:,4);
t2_error = data(:,5);
d2_error = data(:,6);
angle_error = data(:,7);

action = data(:,9);

emg_vl = data(:,11);
emg_rf = data(:,12);
emg_bf = data(:,13);


%Linear Fit
x_fit = 1:length(data);

fitting_emg_vl = polyfit(x_fit, emg_vl, 1);
fitting_emg_rf = polyfit(x_fit, emg_rf, 1);
fitting_emg_bf = polyfit(x_fit, emg_bf, 1);

linefit_emg_vl = polyval(fitting_emg_vl, x_fit);
linefit_emg_rf = polyval(fitting_emg_rf, x_fit);
linefit_emg_bf = polyval(fitting_emg_bf, x_fit);


%% Plots

% figure(1); clf; hold on
% plot(cost)
% title('Online RL Training')
% xlabel('Training Iterations')
% ylabel('Cost')


% figure(2); clf; hold on
% plot(t1_error)
% plot(d1_error)
% plot(t2_error)
% plot(d2_error)
% plot(angle_error)
% title('Errors Online RL Training')
% xlabel('Training Iterations')
% ylabel('Error')
% legend('t1', 'd1', 't2', 'd2', 'angle')


figure(3); clf; hold on; grid on
plot(emg_vl, 'b', 'DisplayName', 'EMG VL')
plot(emg_rf, 'r', 'DisplayName', 'EMG RF')
plot(emg_bf, 'Color', [0.9290 0.6940 0.1250], 'DisplayName', 'EMG BF')
title('EMG Online RL Training')
xlabel('Training Iterations')
ylabel('EMG integral')
legend 'EMG VL' 'EMG RF' 'EMG BF'




% Generate Subfigures with line plots, for paper
figure(4); clf; hold on; grid on

subplot(311)
% subplot(211)
hold on; %grid on
plot(emg_vl, '*b', 'DisplayName', 'EMG VL')
plot(linefit_emg_vl, 'b--')
legend 'EMG VL' 'Linear Fit'
xlabel('Training Iterations')
ylabel('VL EMG Integral')

subplot(312)
hold on; grid on
plot(emg_rf, '*r', 'DisplayName', 'EMG RF')
plot(linefit_emg_rf, 'r--')
legend 'EMG RF' 'Linear Fit'
xlabel('Training Iterations')
ylabel('RF EMG Integral')

subplot(313)
% subplot(212)
hold on; %grid on
plot(emg_bf, '*', 'Color', [0.9290 0.6940 0.1250], 'DisplayName', 'EMG BF')
plot(linefit_emg_bf, '--', 'Color', [0.9290 0.6940 0.1250])
legend 'EMG BF' 'Linear Fit'
xlabel('Training Iterations')
ylabel('BF EMG Integral')


