"""Run browser logic checks with Node.js or macOS JavaScriptCore.

These use a minimal DOM; they do not verify browser layout or painting.
Run: python3 tests/test_traffic_network.py
"""
import ctypes as c
from pathlib import Path
import shutil
import subprocess
import sys

MOCK_DOM = r'''
class Element {
  constructor() { this.value = ''; this.children = []; this.handlers = {}; this.dataset = {}; }
  set value(value) { this._value=String(value); }
  get value() { return this._value; }
  setAttribute(k,v) { this[k]=v; if(k==='data-id') this.dataset.id=String(v); }
  appendChild(el) { this.children.push(el); }
  replaceChildren() { this.children=[]; }
  addEventListener(k,fn) { this.handlers[k]=fn; }
  querySelector(selector) { const id=selector.match(/"(\d+)"/)[1]; return this.children.find(n=>n.dataset.id===id); }
  closest() { return this; }
  focus() {}
  setPointerCapture() {}
  createSVGPoint() { return {x:0,y:0,matrixTransform(){return this;}}; }
  getScreenCTM() { return {inverse(){return {};}}; }
}
const elements = {};
const document = {
  getElementById(id){return elements[id]||(elements[id]=new Element());},
  createElementNS(){return new Element();}, createElement(){return new Element();}
};
const window = {addEventListener(){}};
'''

CHECKS = r'''
function check(value,msg){if(!value)throw Error(msg);}
function click(id){$(id).handlers.click();}
check(nodes.length===6 && roads.length===5, 'Initial network');
check($('nodes').children.length===6, 'SVG nodes drawn');
check(routeForDemand(80).nodes.map(n=>n.name).join(',')==='Start,A,B,End','Initial route');
check($('summary').textContent.includes('114% utilized'), 'Initial bottleneck');
$('demand').value=140; $('demand').handlers.input();
check($('summary').textContent.includes('200% utilized'), 'Demand update');
reset();
selectNode(startId); render();
check(!$('target').children.some(n=>n.value==='0'||n.value==='1'),'Exclude self and existing neighbors');
$('target').value=endId; click('connect');
check(nodes.length===6 && roads.length===6,'Connect existing nodes without adding a node');
check(routeForDemand(80).nodes.length===2,'Shortcut participates in routing');
const shortcut=roadById(selectedRoadId);
check(shortcut.a===startId && shortcut.b===endId,'Correct endpoints');
check($('road').value===String(shortcut.id),'New road selected for capacity editing');
check(addRoad(endId,startId)===null && addRoad(startId,startId)===null,'Reject reverse duplicate and self-loop');
check(addRoad(1000,endId)===null,'Reject missing endpoint');
$('capacity').value=20; $('capacity').handlers.input();
check(shortcut.capacity===20,'Edit connection capacity');
check(routeForDemand(80).nodes.length===4,'Congested shortcut avoided');
click('delete-road');
check(nodes.length===6 && roads.length===5,'Delete only selected road');
selectNode(4); render(); click('add');
const added=selectedId;
check(nodes.length===7 && roads.length===6,'Add new intersection with road');
$('target').value=endId; click('connect');
check(nodes.length===7 && roads.length===7,'New intersection connects to existing End');
click('delete');
check(!byId(added) && roads.length===5 && nodes.length===6,'Delete intersection and attached roads');
check(roads.every(r=>byId(r.a)&&byId(r.b)),'No dangling endpoints');
selectNode(startId); render(); click('delete'); check(nodes.length===6,'Protect Start');
selectNode(endId); render(); click('delete'); check(nodes.length===6,'Protect End');
click('delete-road');
check(routeForDemand(80).nodes.length===0 && $('summary').textContent.includes('No route'),'Disconnected End reported');
$('target').value=startId; click('connect');
check(routeForDemand(80).nodes.length===2,'Restore route after disconnect');
reset(); selectNode(4); render(); click('end');
check(endId===4 && routeForDemand(80).nodes.map(n=>n.name).join(',')==='Start,A,C','Move End');
reset();
const target=$('nodes').children.find(n=>n.dataset.id==='1');
svg.handlers.pointerdown({target,clientX:280,clientY:210,pointerId:1});
svg.handlers.pointermove({clientX:340,clientY:250,pointerId:1});
check(byId(1).x===340&&byId(1).y===250,'Dragging geometry');
svg.handlers.pointerup(); check(drag===null,'Dragging stops');
// Known graph: short narrow road vs longer wide detour, including a loop.
nodes=[]; roads=[]; nextId=0; nextRoadId=0;
startId=addNode('Start',0,0).id; endId=addNode('End',200,0).id;
const via=addNode('Via',100,100);
addRoad(startId,endId,20); addRoad(startId,via.id,200); addRoad(via.id,endId,200);
check(routeForDemand(10).nodes.length===2,'Low demand takes short route');
check(routeForDemand(180).nodes.length===3,'High demand takes wide detour');
check(Math.abs(routeForDemand(180).time-2*Math.SQRT2*(1+.15*.9**4))<1e-9,'Travel time sums chosen route');
const originalStart=startId; startId=endId; endId=originalStart;
check(routeForDemand(180).nodes.length===3,'Roads usable in reverse');
reset(); check(nodes.length===6&&roads.length===5&&endId===3&&Number($('demand').value)===80,'Reset');
'PASS: network creation, connections, cycle-safe routing, capacity, deletion, disconnection, bidirectional roads, dragging, reset';
'''


def run_javascript(source):
    node = shutil.which('node')
    if node:
        subprocess.run([node, '-e', source], check=True)
        return
    if sys.platform != 'darwin':
        raise SystemExit('Install Node.js to run these checks outside macOS.')
    lib = c.CDLL('/System/Library/Frameworks/JavaScriptCore.framework/JavaScriptCore')
    ptr = c.c_void_p
    signatures = {
        'JSGlobalContextCreate': ([ptr], ptr),
        'JSStringCreateWithUTF8CString': ([c.c_char_p], ptr),
        'JSEvaluateScript': ([ptr, ptr, ptr, ptr, c.c_int, c.POINTER(ptr)], ptr),
        'JSValueToStringCopy': ([ptr, ptr, c.POINTER(ptr)], ptr),
        'JSStringGetMaximumUTF8CStringSize': ([ptr], c.c_size_t),
        'JSStringGetUTF8CString': ([ptr, c.c_char_p, c.c_size_t], c.c_size_t),
        'JSStringRelease': ([ptr], None),
        'JSGlobalContextRelease': ([ptr], None),
    }
    for name, (args, result) in signatures.items():
        getattr(lib, name).argtypes = args
        getattr(lib, name).restype = result
    ctx = lib.JSGlobalContextCreate(None)
    script = lib.JSStringCreateWithUTF8CString(source.encode())
    error = ptr()
    result = lib.JSEvaluateScript(ctx, script, None, None, 1, c.byref(error))
    message = lib.JSValueToStringCopy(ctx, error.value or result, None)
    size = lib.JSStringGetMaximumUTF8CStringSize(message)
    buf = c.create_string_buffer(size)
    lib.JSStringGetUTF8CString(message, buf, size)
    text = buf.value.decode()
    lib.JSStringRelease(message)
    lib.JSStringRelease(script)
    lib.JSGlobalContextRelease(ctx)
    if error.value:
        raise AssertionError(text)


if __name__ == '__main__':
    page = (Path(__file__).resolve().parents[1] / 'traffic_tree_toy.html').read_text()
    script = page.split('<script>')[1].split('</script>')[0]
    run_javascript(MOCK_DOM + script + CHECKS)
    print('PASS: connections, routing, capacity, deletion, disconnection, dragging, reset')
