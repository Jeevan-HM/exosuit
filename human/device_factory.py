"""Build the reduced pneumatic suit while preserving the old bare-hinge API."""
from .assistance import AssistanceConfig,KneeAssistance
from .pneumatic import BankParameters,PneumaticExosuitConfig,PneumaticExosuit
from .exosuit_mechanics import DeviceMechanics
from .exosuit_visuals import ExosuitGeometry


def validate_exosuit(config):
    suit=config.get('exosuit',{})
    if not isinstance(suit,dict):raise ValueError('exosuit must be an object')
    if not isinstance(suit.get('enabled',False),bool):raise ValueError('exosuit.enabled must be boolean')
    if suit.get('enabled',False):
        DeviceMechanics(**suit.get('mechanics',{})).validate()
        ExosuitGeometry(**suit.get('geometry',{})).validate()
        if suit.get('mechanics',{}).get('side','l')!='l':
            raise ValueError('Current exosuit is attached to the left knee')
        make_device(config)


def make_device(config):
    a=AssistanceConfig(**config['assistance']);a.validate()
    suit=config.get('exosuit',{})
    if not suit.get('enabled',False):return KneeAssistance(a)
    p=suit.get('pneumatics',{})
    defaults=dict(gain_nm_per_psi=a.torque_gain_nm_per_psi,
                  maximum_torque_nm=a.maximum_torque_nm,
                  max_pressure_psi=p.get('max_pressure_psi',30.),
                  rise_tau_s=p.get('rise_time_constant_s',.08),
                  exhaust_tau_s=p.get('exhaust_time_constant_s',.12))
    banks={name:BankParameters(**(defaults|p.get(name,{}))) for name in ('extension','flexion')}
    return PneumaticExosuit(PneumaticExosuitConfig(stance_psi=a.stance_psi,swing_psi=a.swing_psi,
                    legacy_bank=a.direction,command_rate_hz=a.command_rate_hz,
                    maximum_net_torque_nm=a.maximum_torque_nm,
                    passive_damping_nm_s_per_rad=0.,**banks))
