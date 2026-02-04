import bpy
import ptvsd
ptvsd.enable_attach()
ptvsd.wait_for_attach()

for ob in bpy.data.objects:
    print(ob.name)

