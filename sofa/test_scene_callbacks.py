"""Python scene/controller checks using a minimal SOFA test double.

These tests do not validate SOFA plugins, solvers, component factory names,
or native physics. Run run_headless.py in SOFA to validate those.
"""
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class Data:
    def __init__(self,value):self.value=value


class Component:
    def __init__(self,name="component",**kwargs):
        self._name=name
        for k,v in kwargs.items():setattr(self,k,Data(v))
    def addData(self,name,type,value,**kwargs):setattr(self,name,Data(value))
    def findData(self,name):return getattr(self,name)


class Node:
    def __init__(self,name="root"):
        self.name=name;self.children={};self.objects={}
        self._dt=Data(1/600);self.time=Data(0.);self._gravity=Data([0,0,0]);self._animate=Data(False)
    @property
    def dt(self):return self._dt
    @dt.setter
    def dt(self,v):self._dt.value=v
    @property
    def gravity(self):return self._gravity
    @gravity.setter
    def gravity(self,v):self._gravity.value=v
    @property
    def animate(self):return self._animate
    @animate.setter
    def animate(self,v):self._animate.value=v
    def addChild(self,name):
        child=Node(name);self.children[name]=child;return child
    def getChild(self,name):return self.children[name]
    def addObject(self,obj,**kwargs):
        if isinstance(obj,str):
            name=kwargs.pop('name',obj);obj=Component(name,**kwargs)
        self.objects[obj._name]=obj;return obj
    def getObject(self,name):return self.objects[name]


def load_scene(name):
    sofa=types.ModuleType('Sofa');sofa.Core=types.SimpleNamespace(Controller=Component)
    spec=importlib.util.spec_from_file_location('_callback_test_'+name,Path(__file__).parent/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'Sofa':sofa}):spec.loader.exec_module(module)
    return module


class SceneCallbackTests(unittest.TestCase):
    def test_knee_python_callbacks(self):
        scene=load_scene('knee_exosuit');root=Node()
        with tempfile.TemporaryDirectory() as tmp:
            scene.createScene(root,visuals=True,log_path=Path(tmp)/'trace.csv')
            ctrl=root.getObject('ExosuitControls_PSI');ctrl.live_path=Path(tmp)/'live.json'
            try:
                ctrl.onAnimateBeginEvent({});ctrl.onAnimateEndEvent({})
                self.assertGreater(ctrl.p1Psi.value,0)
                self.assertEqual(len(root.getChild('KneeDynamics').getObject('appliedTorque').forces.value[0]),1)
                ctrl.onKeypressedEvent({'key':'F'});root.time.value=1/300
                ctrl.onAnimateBeginEvent({});ctrl.onAnimateEndEvent({})
                self.assertEqual(ctrl.plant.command,(10,0))
                ctrl.profile.value='heuristic';root.time.value=.01
                ctrl.onAnimateBeginEvent({})
                self.assertEqual(ctrl.pressureAmplitudePsi.value,5)
                ctrl.manualP0Psi.value=float('nan');root.time.value=.02
                ctrl.onAnimateBeginEvent({})
                self.assertFalse(ctrl.plant.cfg['actuation_enabled'])
                self.assertEqual(ctrl.plant.command,(0,0))
            finally:ctrl.close_log()

    def test_fem_python_pressure_conversion(self):
        scene=load_scene('chamber_fem');root=Node();scene.createScene(root,visuals=True)
        ctrl=root.getObject('ChamberPressure_PSI');ctrl.targetPsi.value=10
        for i in range(150):root.time.value=i/600;ctrl.onAnimateBeginEvent({})
        self.assertAlmostEqual(ctrl.measuredPsi.value,10*(1-math.exp(-1)))
        traction=root.getChild('IllustrativeChamber_FEM').getChild('ClosedCavity').getObject('tractionPa')
        self.assertAlmostEqual(traction.pressure.value,ctrl.measuredPsi.value*6894.757293168)


if __name__=='__main__':unittest.main(verbosity=2)
