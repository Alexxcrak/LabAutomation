import pyvisa

rm = pyvisa.ResourceManager("@py")
resources = rm.list_resources()
print("Instrumentos detectados:")
for r in resources:
    print(r)
