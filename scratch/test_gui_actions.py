import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from pulse_lab import _load_preset, _export_kicad_netlist, _generate_pcb, _export_gerbers

def run_tests():
    print("1. Cargando preset 'basic_rc'...")
    graph = _load_preset('basic_rc')
    print(f"   ✓ OK (nodos: {len(graph.all_nodes)}, componentes: {len(graph.components)})")

    print("\n2. Probando _export_kicad_netlist...")
    try:
        res1 = _export_kicad_netlist(graph, out_dir="output/test_netlist")
        if 'error' in res1:
            print(f"   ❌ ERROR: {res1['error']}")
        else:
            print(f"   ✓ OK. Netlist generada en: {res1.get('netlist')}")
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")

    print("\n3. Probando _generate_pcb...")
    try:
        res2 = _generate_pcb(graph, out_dir="output/test_gen_pcb")
        if 'error' in res2:
            print(f"   ❌ ERROR: {res2['error']}")
        else:
            pcb = res2.get('pcb')
            print(f"   ✓ OK. PCB Generado en: {res2.get('path')}")
            print(f"   Stats: {res2.get('stats')}")
            
            print("\n4. Probando export_enclosure sobre el pcb resultante...")
            try:
                from pathlib import Path
                eng_res = pcb.export_enclosure(Path("output/test_gen_pcb/enclosures"))
                print(f"   ✓ OK. Caja generada en: {eng_res['scad_file']}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"   ❌ EXCEPTION Enclosure: {e}")

            print("\n5. Probando AI DRC Review sobre el pcb resultante...")
            try:
                from knowledge.layout_reviewer import LayoutReviewer
                rev = LayoutReviewer(pcb)
                r = rev.audit()
                print(f"   ✓ OK. DRC Pasado: {r['passed']} (Criticos: {len(r['critical_issues'])})")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"   ❌ EXCEPTION DRC: {e}")

            print("\n6. Probando _export_gerbers sobre el pcb resultante...")
            try:
                res3 = _export_gerbers(res2.get('path'))
                if 'error' in res3:
                    print(f"   ❌ ERROR: {res3['error']}")
                else:
                    print(f"   ✓ OK. Gerbers: {res3.get('summary', 'Completado')}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"   ❌ EXCEPTION Gerber export: {e}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"   ❌ EXCEPTION PCB Gen: {e}")

    print("\n✅ TEST COMPLETADO")

if __name__ == "__main__":
    run_tests()
