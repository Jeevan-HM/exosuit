import copy
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


device = torch.device("cpu")
hidden_neuron = 32
#ACTOR NETWORK
class Actor(nn.Module):
    def __init__(self, state_dim, action_dim, max_action):
        super(Actor, self).__init__()

        self.l1 = nn.Linear(state_dim, hidden_neuron)
        self.l2 = nn.Linear(hidden_neuron, hidden_neuron)
        self.l3 = nn.Linear(hidden_neuron, action_dim)

        self.max_action = max_action



    def forward(self, state):
        a = F.relu(self.l1(state))
        a = F.relu(self.l2(a))
        return self.max_action * torch.tanh(self.l3(a))


class Critic(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(Critic, self).__init__()


        # Q1 architecture
        self.l1 = nn.Linear(state_dim + action_dim, hidden_neuron)
        self.l2 = nn.Linear(hidden_neuron, hidden_neuron)
        self.l3 = nn.Linear(hidden_neuron, 1)


        # Q2 architecture
        self.l4 = nn.Linear(state_dim + action_dim, hidden_neuron)
        self.l5 = nn.Linear(hidden_neuron, hidden_neuron)
        self.l6 = nn.Linear(hidden_neuron, 1)




    def forward(self, state, action):
        sa = torch.cat([state, action], 1)


        q1 = F.relu(self.l1(sa))
        q1 = F.relu(self.l2(q1))
        q1 = self.l3(q1)


        q2 = F.relu(self.l4(sa))
        q2 = F.relu(self.l5(q2))
        q2 = self.l6(q2)
        return q1, q2




    def Q1(self, state, action):
        sa = torch.cat([state, action], 1)


        q1 = F.relu(self.l1(sa))
        q1 = F.relu(self.l2(q1))
        q1 = self.l3(q1)
        return q1



class TDR(object):
    def __init__(self, state_dim, action_dim, max_action, discount=0.95, tau=0.1,
              policy_noise=0.1, noise_clip=0.2,policy_freq=4):

        self.adam_lr_a = 5e-3
        self.adam_lr_c = 5e-3#1e-3
        self.actor = Actor(state_dim, action_dim, max_action).to(device)
        self.actor_target = copy.deepcopy(self.actor)
        self.actor_optimizer = torch.optim.Adam(self.actor.parameters(), lr=self.adam_lr_a)

        self.critic = Critic(state_dim, action_dim).to(device)
        self.critic_target = copy.deepcopy(self.critic)
        self.critic_optimizer = torch.optim.Adam(self.critic.parameters(), lr=self.adam_lr_c)

        # FIX (Bug #4): keep max_action so action clamping uses it instead of a
        # hardcoded (-1, 1). Harmless today (max_action == 1) but correct in general.
        self.max_action = max_action

        self.discount = discount
        self.tau = tau
        self.noise_clip = noise_clip
        self.policy_freq = policy_freq
        self.policy_noise = policy_noise

        self.update_count = 0

    def select_action(self, state):
        state = torch.FloatTensor(state.reshape(1, -1)).to(device)
        return self.actor(state).cpu().data.numpy().flatten()


    def train(self, replay_buffer, batch_size=1, step=1):
        # Sample replay buffer
        state, action, next_state, reward, not_done = replay_buffer.sample(batch_size)

        with torch.no_grad():
            # Select action according to policy and add clipped noise
            noise = (
                torch.randn_like(action) * self.policy_noise
            ).clamp(-self.noise_clip, self.noise_clip)

            # FIX (Bug #4): clamp to (-max_action, max_action), not a literal (-1, 1).
            next_action = (self.actor_target(next_state) + noise).clamp(-self.max_action, self.max_action)

            # Compute the target Q value (twin critics)
            target_Q1, target_Q2 = self.critic_target(next_state, next_action)

            # FIX (Bug #5): twin-critic target selection.
            # The original picked one critic by a TD-error heuristic
            # (torch.where(td_tq1 ?? td_tq2, ...)), which can amplify value
            # mis-estimation. Here `reward` is actually a COST to be minimised,
            # so the pessimistic (TD3-equivalent) choice is the element-wise MAX
            # of the two target critics -- it guards against UNDER-estimating
            # future cost. (For a standard reward formulation this would be min.)
            target_Q = torch.max(target_Q1, target_Q2)

            # FIX (Bug #3): mask the bootstrap with not_done so a terminal step
            # does not bootstrap past the end of an episode. Safe no-op while
            # done == 0 everywhere, but correct if a terminal flag is ever set.
            target_Q = reward + not_done * self.discount * target_Q


        # Get current Q estimates
        current_Q1, current_Q2 = self.critic(state, action)
        # Compute critic loss
        critic_loss = F.mse_loss(current_Q1, target_Q) + F.mse_loss(current_Q2, target_Q)

        # Optimize the critic
        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        self.critic_optimizer.step()
        ### delayed policy / target update (fires every policy_freq steps)
        if step % self.policy_freq == 0:
            # Compute actor loss
            self.update_count = self.update_count+1
            # print(self.update_count)

            # FIX (actor-loss sign): `reward` holds a positive COST, so the
            # critic's Q is expected cumulative cost (want it SMALL). The Adam
            # optimizer MINIMIZES actor_loss, so to push the actor toward low
            # cost the loss must be +Q (NOT -Q). Using -Q would train the actor
            # to MAXIMIZE cost. (If you ever switch to storing reward = -cost,
            # then flip this back to -Q to match standard TD3.)
            actor_loss = self.critic.Q1(state, self.actor(state)).mean()

            # Optimize the actor
            self.actor_optimizer.zero_grad()
            actor_loss.backward()
            self.actor_optimizer.step()

            # Update the frozen target models
            for param, target_param in zip(self.critic.parameters(), self.critic_target.parameters()):
                target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)

            for param, target_param in zip(self.actor.parameters(), self.actor_target.parameters()):
                target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)


    def save(self, filename):
        torch.save(self.critic.state_dict(), filename + "_critic")
        torch.save(self.critic_optimizer.state_dict(), filename + "_critic_optimizer")

        torch.save(self.actor.state_dict(), filename + "_actor")
        torch.save(self.actor_optimizer.state_dict(), filename + "_actor_optimizer")


    def load(self, filename):
        self.critic.load_state_dict(torch.load(filename + "_critic"))
        self.critic_optimizer.load_state_dict(torch.load(filename + "_critic_optimizer"))
        self.critic_target = copy.deepcopy(self.critic)

        self.actor.load_state_dict(torch.load(filename + "_actor"))
        self.actor_optimizer.load_state_dict(torch.load(filename + "_actor_optimizer"))
        self.actor_target = copy.deepcopy(self.actor)
