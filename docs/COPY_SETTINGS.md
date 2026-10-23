# Copy settings between Arraytron nodes (v1.23.0)

**Button.** Prototypes tab, section COPY SETTINGS: *Import Settings* copies the settings of the *Source Node* onto this node. Leave Source Node empty and the button looks for another Arraytron node in the same network: the one wired to the same input first, then the one with the most changed settings (a node still at its defaults has nothing to import), then the newest version. *Last Import* says what was copied and what had no counterpart. One undo step.

**Code.**
```python
n = hou.node('/stage/arraytron1')
n.hdaModule().import_settings(n)                         # the button
n.hdaModule().import_settings(n, '/stage/Arraytron')     # from a given node
report = n.hdaModule().copy_settings('/stage/arraytron1', '/stage/Arraytron')   # {'copied': [...], 'missing': [...], 'failed': [...]}
```
`copy_settings(dst, src, only_changed=False)`: only_changed copies just the parameters that are not at their default on src. dst and src may be any Arraytron versions; the function lives in the module of the new node, so a node of an old release is a valid target or source.

**What is copied.** Settings matched by name: numbers, text, toggles, menus, ramps and animation (keyframes). Not copied: buttons, labels, read-outs (parameters with a default expression), the tab state and this section. Multiparm counters (Prototype Bank, override table ...) are copied first so their rows exist. The one renamed parameter of the first releases, Prototype, becomes row 1 of the Prototype Bank. A parameter the other node does not have is listed under *missing*, never an error. Expressions are copied as their value.

**Evidence.** `tests/validate_copy.py`. On the legacy nodes of a shot (two v0.15 nodes, one Prototype each) the import copied 39 settings and the new node produced the same instances as the old one.
