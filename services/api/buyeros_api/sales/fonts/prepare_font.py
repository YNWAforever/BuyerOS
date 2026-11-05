"""Auditable one-time font derivation, not an application/runtime installer.

Invoke with the pinned source path and explicit output path. Requires the
fonttools==4.68.0 already pinned transitively by this checkout's uv.lock.
No network, upstream scripts, shell execution, or runtime font lookup.
"""
import hashlib
from pathlib import Path
import sys
import fontTools
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


def main(source, destination):
    assert fontTools.__version__=='4.68.0'
    source=Path(source)
    assert hashlib.sha256(source.read_bytes()).hexdigest()=='70172afd2cf0e045182787219b949e7798253982a36e364114757c09efd55477'
    font=TTFont(source,recalcTimestamp=False)
    assert {a.axisTag for a in font['fvar'].axes}=={'wght'}
    font=instantiateVariableFont(font,{'wght':400},inplace=True)
    assert 'fvar' not in font and 'glyf' in font
    names={1:'BuyerOS HK',2:'Regular',3:'BuyerOSHK-Regular-1.0',4:'BuyerOS HK Regular',6:'BuyerOSHK-Regular',
        16:'BuyerOS HK',17:'Regular',25:'BuyerOSHK'}
    for record in list(font['name'].names):
        if record.nameID in names:
            font['name'].setName(names[record.nameID],record.nameID,record.platformID,record.platEncID,record.langID)
    if 'DSIG' in font: del font['DSIG']
    font.recalcTimestamp=False
    font.save(destination)
    print(hashlib.sha256(Path(destination).read_bytes()).hexdigest())


if __name__=='__main__': main(*sys.argv[1:])
