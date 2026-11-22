%% Plots results of online RL 

clc; clear;

filename = 'training_6_22_30psi.csv'
% filename = 'training_6_22_offline1.csv'

data = readmatrix(filename);

cost = data(:,2);
t1_error = data(:,3);
d1_error = data(:,4);
t2_error = data(:,5);
d2_error = data(:,6);
angle_error = data(:,7);


% figure(1); clf; hold on
% plot(cost)
% title('Online RL Training')
% xlabel('Training Itterations')
% ylabel('Cost')


figure(2); clf; hold on
plot(t1_error)
plot(d1_error)
plot(t2_error)
plot(d2_error)
plot(angle_error)
title('Errors Online RL Training')
xlabel('Training Itterations')
ylabel('Error')
legend('t1', 'd1', 't2', 'd2', 'angle')


