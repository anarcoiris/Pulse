// PulseLab Forge Enclosure for: ESP8266 Sensor Node
// Auto-generated parametric model

/* [Parámetros Generales] */
board_w = 60.0;
board_h = 45.0;
wall = 2.0;
clearance = 0.5;
standoff_h = 5.0;
base_z = 2.0;
lip_h = 2.0;
total_inner_h = standoff_h + 15; // Altura interior total aproximada

$fn = 50;

// Cálculos derivados
inner_w = board_w + clearance * 2;
inner_h = board_h + clearance * 2;
outer_w = inner_w + wall * 2;
outer_h = inner_h + wall * 2;

module rounded_rect(w, h, r, height) {
    hull() {
        translate([r, r, 0]) cylinder(r=r, h=height);
        translate([w-r, r, 0]) cylinder(r=r, h=height);
        translate([w-r, h-r, 0]) cylinder(r=r, h=height);
        translate([r, h-r, 0]) cylinder(r=r, h=height);
    }
}

module boss() {
    difference() {
        cylinder(h=standoff_h, d=6); // Pilar externo
        translate([0,0,-1]) cylinder(h=standoff_h+2, d=2.8); // Agujero para tornillo autorroscante M3
    }
}

module bottom_shell() {
    difference() {
        // Base exterior sólida
        translate([-wall - clearance, -wall - clearance, 0])
            rounded_rect(outer_w, outer_h, 3, base_z + standoff_h + lip_h);
        
        // Vaciado interior principal
        translate([-clearance, -clearance, base_z])
            rounded_rect(inner_w, inner_h, 2, standoff_h + lip_h + 1);
            
        // Vaciado para escalón de encaje (Lip)
        translate([-clearance - wall/2, -clearance - wall/2, base_z + standoff_h])
            rounded_rect(inner_w + wall, inner_h + wall, 2, lip_h + 1);
    }
    
    // Añadir Pilares de montaje
    translate([3.500, 3.500, base_z]) boss();
    translate([56.500, 3.500, base_z]) boss();
    translate([3.500, 41.500, base_z]) boss();
    translate([56.500, 41.500, base_z]) boss();
}

module top_shell() {
    // Parte superior de la caja (tapa)
    top_h = total_inner_h - standoff_h;
    translate([0, outer_h + 10, 0]) { // Mover a un lado
        difference() {
            // Techo exterior
            translate([-wall - clearance, -wall - clearance, 0])
                rounded_rect(outer_w, outer_h, 3, base_z + top_h);
            
            // Vaciado interior
            translate([-clearance, -clearance, base_z])
                rounded_rect(inner_w, inner_h, 2, top_h + 1);
        }
        // Borde de encaje (Rim)
        translate([-clearance - wall/2 + 0.1, -clearance - wall/2 + 0.1, base_z + top_h])
            difference() {
                rounded_rect(inner_w + wall - 0.2, inner_h + wall - 0.2, 2, lip_h);
                translate([wall/2, wall/2, -1])
                    rounded_rect(inner_w - 0.2, inner_h - 0.2, 1, lip_h + 2);
            }
    }
}

// Representación unificada
bottom_shell();
top_shell();