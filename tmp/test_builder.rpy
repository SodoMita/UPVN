define e = Character("Eileen", color="#c8ffc8")

label start:
    scene bg classroom
    e "Hello from builder"
    camera zoom 1.5 duration 1.0 with ease
    load_stage classroom_3d
    show3d eileen at marker_eileen
