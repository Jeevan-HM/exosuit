import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from collections import Counter
from control import (PressureReplay,heuristic_timings,pressure_for_phase,
                     timings_from_normalized_action,validate_timings)
from plant import ExosuitPlant,TorqueTable,load_config,validate_config
from reference_run import simulate
from units import PA_PER_PSI,psi_to_pa,pa_to_psi
from chamber_mesh import generate_chamber,signed_volume
from geometry import SuitGeometry
from sim_adapter import write_sim_command

BASE=Path(__file__).resolve().parent


class ControlTests(unittest.TestCase):
    def test_psi_conversion(self):
        self.assertAlmostEqual(psi_to_pa(10),68947.57293168)
        for p in (0,5,10,20):self.assertAlmostEqual(pa_to_psi(psi_to_pa(p)),p)
        for bad in (float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):psi_to_pa(bad)

    def test_original_switches_and_end_venting(self):
        times=(.13,.264,.632,1.27)
        expected=[(0,(0,10)),(.129,(0,10)),(.13,(10,0)),(.263,(10,0)),
                  (.264,(0,10)),(.631,(0,10)),(.632,(10,0)),(1.269,(10,0)),
                  (1.27,(0,0)),(2,(0,0))]
        for t,answer in expected:self.assertEqual(pressure_for_phase(t,times,10),answer)

    def test_rl_action_units(self):
        low=timings_from_normalized_action([-1]*4,2)
        high=timings_from_normalized_action([1]*4,2)
        for a,b in zip(low,(.1,.42,1,1.8)):self.assertAlmostEqual(a,b)
        for a,b in zip(high,(.4,.82,1.4,2)):self.assertAlmostEqual(a,b)
        for bad in ([2,0,0,0],[0,0,0],[float('nan')]*4):
            with self.assertRaises(ValueError):timings_from_normalized_action(bad,1.27)

    def test_heuristic(self):
        a=heuristic_timings([15,50,80],1.1)
        for x,y in zip(a,(.165,.55,.88,1.1)):self.assertAlmostEqual(x,y)
        self.assertEqual(pressure_for_phase(.2,a,5),(5,0))
        for bad in ([.2,.1,.6,1],[0,.2,.6,1],[.1,.2,.6,2]):
            with self.assertRaises(ValueError):validate_timings(bad,1.27)

    def test_replay(self):
        r=PressureReplay(BASE/'examples/pressure_replay.csv',20)
        self.assertEqual(r.command(.13),(10,0));self.assertEqual(r.command(1.5),(0,0))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.csv'
            path.write_text('time_s,p0_psi,p1_psi\n0,10,0\n0,0,10\n')
            with self.assertRaises(ValueError):PressureReplay(path,20)
            path.write_text('time_s,p0_psi,p1_psi\n0,nan,0\n')
            with self.assertRaises(ValueError):PressureReplay(path,20)

    def test_file_adapter(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'command.json'
            result=write_sim_command(pressure_psi=[5,10],path=path)
            self.assertEqual(json.loads(path.read_text()),result)
            result=write_sim_command(timings_s=[.13,.264,.632,1.27],path=path)
            self.assertEqual(result['mode'],'timed')
            self.assertEqual(list(Path(d).glob('.sim-command-*')),[])


class PlantTests(unittest.TestCase):
    def test_measured_grid_and_interpolation(self):
        t=TorqueTable(BASE/'data/torque_calibration.json')
        for bank in ('flexion','extension'):
            for i,angle in enumerate(t.angles):
                for j,p in enumerate(t.pressures):
                    self.assertAlmostEqual(t.torque(bank,angle,p),t.data[bank]['mean_nm'][i][j])
            g=t.data[bank]['mean_nm']
            self.assertAlmostEqual(t.torque(bank,22.5,7.5),sum(g[i][j] for i in (1,2) for j in (1,2))/4)
        self.assertEqual(t.torque('flexion',90,20),0)
        self.assertEqual(t.torque('extension',0,20),0)

    def test_pressure_lag_and_venting(self):
        c=load_config();c.update(mode='manual',manual_pressure_psi=[10,0])
        p=ExosuitPlant(c)
        for i in range(150):out=p.applied_torque(i/600,.5,0,1/600)
        self.assertAlmostEqual(out['p0_psi'],10*(1-math.exp(-1)),places=10)
        before=p.pressure[0];p.cfg['actuation_enabled']=False
        out=p.applied_torque(.25,.5,0,1/600)
        self.assertGreater(out['p0_psi'],0);self.assertLess(out['p0_psi'],before)
        self.assertEqual(out['p0_command_psi'],0)
        self.assertAlmostEqual(out['p0_pa']/out['p0_psi'],PA_PER_PSI)

    def test_mapping(self):
        c=load_config();c.update(mode='manual',manual_pressure_psi=[10,0],gravity_m_s2=0)
        p=ExosuitPlant(c)
        self.assertGreater(p.applied_torque(0,math.pi/4,0,1/600)['suit_torque_nm'],0)
        c['channel_map']=['extension','flexion'];p=ExosuitPlant(c)
        self.assertLess(p.applied_torque(0,math.pi/4,0,1/600)['suit_torque_nm'],0)

    def test_data_domain_and_invalid_config(self):
        for key,value in [('max_pressure_psi',21),('max_angle_deg',91)]:
            c=load_config();c[key]=value
            with self.assertRaises(ValueError):ExosuitPlant(c)
        for key,value in [('dt_s',0),('fill_time_constant_s',0),('mass_kg',float('nan')),
                          ('channel_map',['flexion','flexion']),('mode','unknown')]:
            c=load_config();c[key]=value
            with self.assertRaises(ValueError):validate_config(c)

    def test_tracking_and_long_runs_remain_finite(self):
        for profile in ('rl','heuristic'):
            for mapping in (['flexion','extension'],['extension','flexion']):
                for tracked in (False,True):
                    c=load_config();c.update(profile=profile,channel_map=mapping,wearer_tracking=tracked)
                    if profile=='heuristic':c['pressure_amplitude_psi']=5
                    out=simulate(c,10)
                    self.assertTrue(0<=out['angle_deg']<=90)
                    for row in out['rows']:
                        for k,v in row.items():
                            if v is not None:self.assertTrue(math.isfinite(v),k)
                        self.assertTrue(0<=row['p0_psi']<=20 and 0<=row['p1_psi']<=20)

    def test_zero_load_preserves_rest(self):
        c=load_config();c.update(actuation_enabled=False,gravity_m_s2=0,
                               damping_nm_s_per_rad=0,passive_stiffness_nm_per_rad=0)
        self.assertAlmostEqual(simulate(c,1)['angle_deg'],c['initial_angle_deg'])


class MeshTests(unittest.TestCase):
    def test_chamber_orientation_and_closed_cavity(self):
        m=generate_chamber();p=m['positions'];surface=m['cavity_triangles'];cp=m['cavity_positions']
        self.assertTrue(all(signed_volume(*(p[i] for i in t))>0 for t in m['tetrahedra']))
        edges=Counter(tuple(sorted((a,b))) for f in surface for a,b in zip(f,f[1:]+f[:1]))
        self.assertTrue(all(n==2 for n in edges.values()))
        volume=sum(signed_volume([0,0,0],*(cp[i] for i in f)) for f in surface)
        self.assertAlmostEqual(volume,m['cavity_volume_m3'],places=12)
        resultant=[0.,0.,0.]
        for face in surface:
            a,b,c=[cp[i] for i in face];u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
            for i in range(3):resultant[i]+=(u[(i+1)%3]*v[(i+2)%3]-u[(i+2)%3]*v[(i+1)%3])/2
        for f in resultant:self.assertAlmostEqual(f,0,places=12)

    def test_visual_geometry_indices_and_topology(self):
        g=SuitGeometry(.43)
        initial=None
        for angle in (0,math.pi/4,math.pi/2):
            meshes=g.meshes(angle,5,10,20)
            shapes={name:(len(vertices),len(faces)) for name,(vertices,faces) in meshes.items()}
            if initial is None:initial=shapes
            else:self.assertEqual(initial,shapes)
            for vertices,faces in meshes.values():
                self.assertTrue(all(0<=i<len(vertices) for f in faces for i in f))
                self.assertTrue(all(math.isfinite(v) for p in vertices for v in p))


if __name__=='__main__':unittest.main(verbosity=2)
