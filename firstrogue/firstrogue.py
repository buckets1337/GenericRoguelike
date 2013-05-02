import libtcodpy as libtcod
import math
import textwrap
import shelve

#sets window size
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
#camera params
CAMERA_WIDTH = 80
CAMERA_HEIGHT = 43
#GUI params
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
INVENTORY_WIDTH = 50
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30
#message log params
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
#sets fps
LIMIT_FPS = 20
#world parameters
CRIT_CHANCE = 0.1
#map parameters
MAP_WIDTH = 100
MAP_HEIGHT = 100
#room parameters
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_INTERSECTS = 4
#player params
PLAYER_HP = 100
PLAYER_DEFENSE = 0
PLAYER_POWER = 2
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150
#tile colors
color_dark_wall = libtcod.Color(60,60,60)
color_light_wall = libtcod.Color(133,133,42)
color_dark_ground = libtcod.Color(100,100,100)
color_light_ground = libtcod.Color(210,210,67)
#FOV Settings
FOV_ALGO = 0 #default algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10
#spell params
HEAL_AMOUNT = 40
LIGHTNING_DAMAGE = 40
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25

#########################
#   Object System
#########################

class Object:
    #this is a generic object (item, monster, etc) that is always drawn to screen
    def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None, equipment=None):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.fighter = fighter
        self.always_visible = always_visible
        
        
        if self.fighter:    #let the fighter component know who owns it
            self.fighter.owner = self
            
        self.ai = ai
        if self.ai: #let the AI component know who owns it
            self.ai.owner = self
            
        self.item = item
        if self.item:   #let the item component know who owns it
            self.item.owner = self
            
        self.equipment = equipment
        if self.equipment:  #let equipment component know who owns it
            self.equipment.owner = self
            #Equipment is an item
            self.item = Item()
            self.item.owner = self
        
    def move (self, dx, dy):
        #check for blocked
        if not is_blocked(self.x + dx, self.y + dy):
            #move by the given amount
            self.x += dx
            self.y += dy
            
    def moveai (self, dx, dy):  #currently, if x is free, moves diag, otherwise, takes two turns for diag move
        if not is_blocked(self.x, self.y + dy):
            self.y += dy
        if not is_blocked(self.x + dx, self.y):
            self.x += dx

        
    def draw(self):
        #only show if it's visible to the player
        if libtcod.map_is_in_fov(fov_map, self.x, self.y):
            (x, y) = to_camera_coordinates(self.x, self.y)
            
            if x is not None:
                #sets the color and then draws the character
                libtcod.console_set_default_foreground(con,self.color)
                libtcod.console_put_char(con,x,y,self.char,libtcod.BKGND_NONE)
    
    def clear(self):
        #erase the character that represents the object
        (x, y) = to_camera_coordinates(self.x, self.y)
        if x is not None:
            libtcod.console_put_char(con, x, y, ' ', libtcod.BKGND_NONE)
            
    def move_towards(self, target_x, target_y):
        #vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        #below is old move_towards code (hangs on walls)
        #distance = math.sqrt(dx**2 + dy**2)
        ##normalize vector to length 1, keeping direction, then round
        ##and convert to integer so movement is restricted to the map
        #dx = int(round(dx/distance))
        #dy = int(round(dy/distance))
        if dx>0:
            dx = 1
        if dx<0:
            dx = -1
        if dy>0:
            dy = 1
        if dy<0:
            dy = -1
        self.moveai(dx, dy)

        
    def distance_to(self, other):
        #return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx**2 + dy**2)
        
    def send_to_back(self):
        #make this object drawn first, so everything else appears above it
        global objects
        objects.remove(self)
        objects.insert(0, self)
        
    def distance(self, x, y):
    #return the distance to some coords
        return math.sqrt((x-self.x)**2 + (y-self.y)**2)
        
class Tile:
    #a tile of the map and it's properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
        self.explored = False
        
        #by default, if a tile is blocked, it also blocks los
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight


        
##########  Object Constructors to refine what each object is   

class Fighter:
    #combat-related properties and methods (monsters, player, anything that fights)
    @property
    def power(self):
        bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
        return self.base_power + bonus
    @property
    def defense(self):  #return actual defense, by summing bonuses
        bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
        return self.base_defense + bonus
    @property
    def max_hp(self):
        bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_max_hp + bonus
        
    
    def __init__(self, hp, defense, power, xp, death_function=None):
        self.death_function = death_function
        self.base_max_hp = hp
        self.hp = hp
        self.base_defense = defense
        self.base_power = power
        self.xp = xp
        
    def take_damage(self,damage):
        #apply damage if possible
        if damage > 0:
            self.hp -= damage
        #check for death, if there is a death function call it
        if self.hp <= 0:
            function = self.death_function
            if function is not None:
                function(self.owner)
            if self.owner != player:    #yield xp to player
                player.fighter.xp += self.xp
            
    def attack(self, target, critical_hit=False):
        #apply a random element to attack and defense, and come up with a damage
        power_modifier = (libtcod.random_get_int(0, 1, 100))/100.0
        #if CRIT_CHANCE or below is rolled, create a critical hit
        if power_modifier <= CRIT_CHANCE:
            critical_hit = True
            power_modifier = libtcod.random_get_int(0, 100, 300)/100.0
        defense_modifier = libtcod.random_get_int(0, 50, 150)/100.0
        damage = int(round((self.power/2+self.power*power_modifier) - (target.fighter.defense*defense_modifier)))
        if damage < 1:
            damage = 0
            if critical_hit:
                damage = 1
            flip = libtcod.random_get_int(0, 0, abs(self.power-target.fighter.defense))
            if flip <= 1:
                damage = 1

        if critical_hit:
            message(self.owner.name.capitalize() + ' scores a critical hit for ' + str(damage) + ' damage!', libtcod.yellow)
            target.fighter.take_damage(damage)
        elif damage > 0:
            #make the target take some damage
            if self.owner.name == 'player':
                message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.', libtcod.white)
            else:
                message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.', libtcod.orange)
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!', libtcod.dark_gray)
        
    def heal(self, amount):
        #heal by the given amount, without going over the max
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp
            
            
class BasicMonster:
    #AI for a basic monster
    def take_turn(self):
        # a basic monster takes its turn. If you can't see it, it can't see you
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
            #move toward the player if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
            #close enough, attack! (if the player is alive)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)
                
class ConfusedMonster:
    #AI for a confused monster
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns
        
    def take_turn(self):
        if self.num_turns >0:
            #move in a random direction
            self.owner.move(libtcod.random_get_int(0,-1,1), libtcod.random_get_int(0,-1,1))
            self.num_turns -= 1
        else:   #restore previous AI
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)
        
class Item:
    #an item that can be picked up and used.
    def __init__(self, use_function=None):
        self.use_function = use_function
    def pick_up(self):
        #add to the player's inventory and remove from the map
        if len(inventory) >= 26:
            message('Your inventory is full, you cannot carry ' + self.owner.name + '!', libtcod.yellow)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', libtcod.green)
        #special case: automatically equip, if slot is open
            equipment = self.owner.equipment
            if equipment and get_equipped_in_slot(equipment.slot) is None:
                equipment.equip()
        
    def use(self):
    #special case:if equipment, the use toggles equip status
        if self.owner.equipment:
            self.owner.equipment.toggle_equip()
            return
        #just call the "use function" if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner)    #destroy after use, unless cancelled
            
    def drop(self):
        #add to the map and remove from inventory, placing at players coords
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
    #special case: if it's equipment, de-equip it
        if self.owner.equipment:
            self.owner.equipment.dequip()
        
class Equipment:
    #an object that can be equipped, yeilding bonuses. Automatically adds the item component
    def __init__(self, slot, power_bonus=0, defense_bonus=0, max_hp_bonus=0):
        self.slot = slot
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.max_hp_bonus = max_hp_bonus
        self.is_equipped = False
        
    def toggle_equip(self): #toggle equip/deequip status
        if self.is_equipped:
            self.dequip()
        else:
            self.equip()
            
    def equip(self):
                #if the slot is already being used, de-equip whatever is there first
        old_equipment = get_equipped_in_slot(self.slot)
        if old_equipment is not None:
            old_equipment.dequip()
        #equip object and show a message about it
        self.is_equipped = True
        message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)
        
        
    def dequip(self):
        #deequip object and show a message about it
        if not self.is_equipped: return
        self.is_equipped = False
        message('Removed ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_green)
        
##############################
#   Function Definitions
##############################
        
def make_map():
    global map, objects, stairs, room_no
    
    #starting list of objects
    objects = [player]
    
    #fill map with "blocked" tiles
    map = [[Tile(True)
        for y in range(MAP_HEIGHT) ]
            for x in range(MAP_WIDTH) ]
            
    #carves the rooms
    rooms = []
    num_rooms = 0
    room_intersects = 0
    
    for r in range(MAX_ROOMS):
        #random width and height
        w = libtcod.random_get_int(0,ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0,ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        #random position in bounds on the map
        x = libtcod.random_get_int(0,0,MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0,0,MAP_HEIGHT - h - 1)
        #makes the room
        new_room = Rect(x,y,w,h)
        #check other rooms for an intersection
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                room_intersects +=1
                if room_intersects >= MAX_ROOM_INTERSECTS:
                    failed = True
                    break
                break
        if not failed:
            #this means no intersections, so clear to build
            
            #paint to map's tiles
            create_room(new_room)
            
            #spawn room contents, such as monsters
            place_objects(new_room)
            
            #center coords of room
            (new_x, new_y) = new_room.center()
            
            ########
            #optional room number label
            #room_no = Object(new_x,new_y, chr(65+num_rooms), 'room number', libtcod.white, blocks=False, fighter=None, ai=None)
            #objects.insert(0,room_no) #draw early, so monsters draw on top
            #room_no.always_visible = True
            ########
            
            if num_rooms == 0:
                #this is starting room
                player.x = new_x
                player.y = new_y
                
            else:
                #all rooms after first
                #connect to previous room with tunnel
                
                #center coords of previous room
                (prev_x, prev_y) = rooms[num_rooms-1].center()
                
                #flip a coin
                if libtcod.random_get_int(0,0,1) == 1:
                    #first hor, then vert
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #first vert, then hor
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)
                    
            #append the new room to the list
            rooms.append(new_room)
            num_rooms += 1
    #create stairs at the center of the last room
    stairs = Object(new_x, new_y, '<', 'stairs', libtcod.white)
    objects.append(stairs)
    stairs.send_to_back()   #drawn below monsters
    stairs.always_visible = True
            
def create_room(room):
    global map
    #go through the tiles in the rectangle and make them passable
    for x in range(room.x1+1, room.x2):
        for y in range(room.y1+1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False
            
def create_h_tunnel(x1,x2,y):
    global map
    for x in range(min(x1,x2), max(x1,x2)+1):
        map[x][y].blocked = False
        map[x][y].block_sight = False
        
def create_v_tunnel(y1,y2,x):
    global map
    for y in range(min(y1,y2), max(y1,y2)+1):
        map[x][y].blocked = False
        map[x][y].block_sight = False
        
class Rect:
    #a rectangle on the map.  used to charcterize a room.
    def __init__(self,x,y,w,h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h
        
    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)
        
    def intersect(self, other):
        #returns true if this rectangle intersects with another rectangle
        return(self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)
    
    
def is_blocked(x,y):    #checks if a tile is blocked by something
    #first test the map tile
    if map[x][y].blocked:
        return True
        
    #now check for blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True
            
    return False
    
def player_move_or_attack(dx, dy):  #allows the player to move or attack
    global fov_recompute
    
    #the coords the player is moving to/attacking
    x = player.x + dx
    y = player.y + dy
    
    #try to find an attackable object there
    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break
            
    #attack if target found, move otherwise
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True
        
def player_death(player):
    #the game ended!
    global game_state
    message('You died!', libtcod.red)
    game_state = 'dead'
    
    #for added effect, transform the player into a corpse!
    player.char = '%'
    player.color = libtcod.dark_red
    
def monster_death(monster):
    #transform it into a nasty corpse! it doesn't block, can't be attacked
    #and doesn't move
    message(monster.name.capitalize() + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.', libtcod.sky)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()
    
def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    #render a bar (HP, EXP, ETC) first calculate the width of the bar
    bar_width = int(float(value) / maximum *total_width)
    
    #render the background first
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
    
    #now render the bar on top
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
        
    #centered text with values on bar
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
        name + ': ' + str(value) + '/' + str(maximum))
        
def message(new_msg, color = libtcod.white):
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
    
    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room 
        #for the new line
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]
            
        #add the new line as a tuple, with the text and the color
        game_msgs.append( (line,color) )
        
def target_tile(max_range=None):
    #return the position of a tile left clicked in the FOV(optionally in range) or (None,None) if right clicked
    global key, mouse
    while True:
        #render the screen.  this erases the inventory and shows the names of objects under mouse
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
        render_all()
        
        (x,y) = (mouse.cx, mouse.cy)
        (x,Y) = (camera_x + x, camera_y + y)    #from screen to map coordinates
        
        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map,x,y) and (max_range is None or player.distance(x,y) <= max_range)):
            return(x,y)
            
        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return (None,None)  #cancel if right clicked or escape
            
def target_monster(max_range=None):
    #returns a clicked monster inside FOV up to a range, or None if right clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None:   #cancels
            return None
        #return the first clicked monster, otherwise continue looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj
        
def get_names_under_mouse():
    global mouse
    
    #return a string with the names of all objects under the mouse
    (x, y) = (mouse.cx, mouse.cy)
    #create a list with the names of all objects at mouse position
    names = [obj.name for obj in objects
        if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
    names = ', '.join(names)    #join the names, separated by commas
    return names.capitalize()
    
def move_camera(target_x, target_y):
    global camera_x, camera_y, fov_recompute
    #new camera coords(from top left relative to map)
    x = target_x - CAMERA_WIDTH / 2 #coordinates so that target is at center of screen
    y = target_y - CAMERA_HEIGHT / 2
    
    #make sure camera doesn't see outside the map
    if x < 0: x = 0
    if y < 0: y = 0
    if x > MAP_WIDTH - CAMERA_WIDTH : x = MAP_WIDTH - CAMERA_WIDTH 
    if y > MAP_HEIGHT - CAMERA_HEIGHT : y= MAP_HEIGHT - CAMERA_HEIGHT 
    
    if x != camera_x or y != camera_y: fov_recompute = True
    
    (camera_x, camera_y) = (x, y)
    
def to_camera_coordinates(x, y):
    #convert coordinates on the map to coordinates on the screen
    (x, y) = (x - camera_x, y - camera_y)
    
    if (x < 0 or y < 0 or x >= CAMERA_WIDTH or y>= CAMERA_HEIGHT):
        return (None, None) #if it's outside the view
    return (x, y)
    
def closest_monster(max_range):
    #find closest enemy, up to max range, in the player's fov
    closest_enemy = None
    closest_dist = max_range + 1    #start with more than max range
    
    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            #calculate distance between this object and player
            dist = player.distance_to(object)
            if dist < closest_dist: #it's closer, so remember it
                closest_enemy = object
                closest_dist = dist
    return closest_enemy
    
def check_level_up():
    #see if the player's xp is enough to level up
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        #level up
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', libtcod.yellow)
        choice = None
        while choice == None:   #keep asking until choice is made
            choice = menu('Level up! Choose a stat to raise:\n', ['Constitution', 'Strength', 'Agility'], LEVEL_SCREEN_WIDTH)
        if choice == 0:
            player.fighter.base_max_hp += 20
        elif choice == 1:
            player.fighter.base_power += 1
        elif choice == 2:
            player.fighter.base_defense += 1

def get_all_equipped(obj):  #returns a list of equipped items
    if obj == player:
        equipped_list = []
        for item in inventory:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        return []   #other objects have no equipment
    
def menu(header, options, width):
    if len(options) > 26: raise ValueError("cannot have a menu with more than 26 options")
    #calculate the total height for the header (after auto-wrap) and one line per option
    header_height = libtcod.console_get_height_rect(con, 0,0, width, SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0
    height = len(options) + header_height
    #create an off-screen console that represents the menu's window
    window = libtcod.console_new(width, height)
    
    #print the header, with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0,0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
    #print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1
    #blit the contents of "window" to the root console
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    libtcod.console_blit(window, 0,0, width, height, 0, x, y, 1.0, 0.7)
    #present the root console to the player and wait for a key-press
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)
    
    if key.vk == libtcod.KEY_ENTER and key.lalt:
            # Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
            
        #converts the ASCII code to an index; if it corresponds to an option, return it
    index = key.c - ord('a')
    if index >= 0 and index < len(options): return index
    return None
    
def msgbox(text, width=50):
    menu(text, [], width)   #use menu() as a sort of "message box"
    
        
def inventory_menu(header):
    #show a menu with each item of the inventory as an option
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = []
        for item in inventory:
            text = item.name
            #show additional info if equipped
            if item.equipment and item.equipment.is_equipped:
                text = text + ' (on ' + item.equipment.slot + ')'
            options.append(text)
        
    index = menu(header, options, INVENTORY_WIDTH)
    #if an item was chosen, return it
    if index is None or len(inventory) == 0: return None
    return inventory[index].item
    
def random_choice_index(chances):   #choose one option, returning index
    #the dice will land on some number between 1 and the sum of chances
    dice = libtcod.random_get_int(0, 1, sum(chances))
    
    #go through all chances, keeping sum so far
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w
        
        #see if the dice landed in the part in this choice
        if dice <= running_sum:
            return choice
        choice += 1
        
def random_choice(chances_dict):
    #choose on option from dictionary of chances, returning its key
    chances = chances_dict.values()
    strings = chances_dict.keys()
    return strings[random_choice_index(chances)]
    
def from_dungeon_level(table):
    #returns a value that depends on level. table specifies value at each level
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value
    return 0

def get_equipped_in_slot(slot): #returns eq in slot or None if empty
    for obj in inventory:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None
    
########    Spells and Effects

def cast_heal():
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.red)
        return 'cancelled'
    message('Your wounds start to feel better!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    #find closest enemy inside max range and damage it
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None: #no enemy in range
        message('No enemy is close enough to strike.', libtcod.red)
        return 'cancelled'
        
    #zap it!
    message('A lightning bolt strikes the ' + monster.name + ' for ' + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)
    
def cast_confuse():
    #ask player for a target to confuse
    message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None: return 'cancelled'
    
    #replace the monster's AI with a confused one; after some turns it wears off
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster  #tell the new component who owns it
    message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around.', libtcod.light_green)
    
def cast_fireball():
    #ask the player for a target tile to throw a fireball at
    message('Left-click a target tile for the fireball, or right-click to cancel.', libtcod.light_cyan)
    (x, y) = target_tile()
    if x is None: return 'cancelled'
    message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)
    
    for obj in objects: #damage every fighter in range, including player
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)
    
########## Room Object Generation

def place_objects(room):
        #maximum number of monsters per room
    max_monster = from_dungeon_level([[2,1], [3,4], [5,6]])
        
    #chance of each monster
    monster_chances ={}
    monster_chances['orc'] = 80 #orcs always show up
    monster_chances['troll'] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])
        
    #max number of items in each room
    max_items = from_dungeon_level ([[1, 1], [2,4]])
        
    #chance of each item (by default, chance 0 at lvl 1, which then increases)
    item_chances = {}
    item_chances['heal'] = 35   #healing potions always show up
    item_chances['sword'] = from_dungeon_level([[5, 4]])
    item_chances['shield'] = from_dungeon_level([[15, 8]])
    item_chances['lightning'] = from_dungeon_level([[25, 4]])
    item_chances['fireball'] = from_dungeon_level([[25, 6]])
    item_chances['confuse'] = from_dungeon_level([[10, 2]])
        
    for i in range(max_monster):
        #choose random spot for this monster
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
            
        if not is_blocked(x,y):
            choice = random_choice(monster_chances)
            if choice == 'orc':
                #create an orc
                fighter_component = Fighter(hp=20, defense=0, power=4, xp=36, death_function=monster_death)
                ai_component = BasicMonster()
                    
                monster = Object(x,y,'o', 'orc', libtcod.desaturated_green, blocks=True, fighter=fighter_component, ai=ai_component)
            elif choice == 'troll':
                #create a troll
                fighter_component = Fighter(hp=30, defense=2, power=8, xp=100, death_function=monster_death)
                ai_component = BasicMonster()
                    
                monster = Object(x,y,'T', 'troll', libtcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component)
                
            objects.append(monster)
        
        
    for i in range(max_items):
        #choose a random spot for this item
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
            
        #only place it if the tile is not blocked
        if not is_blocked(x, y):
                
            choice = random_choice(item_chances)
            if choice == 'heal':
                #create a healing potion
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, '!', 'healing potion', libtcod.violet, item=item_component)
            elif choice == 'lightning':
                #creates a lightning bolt scroll
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, '#', 'scroll of lightning bolt', libtcod.light_yellow, item=item_component)
            elif choice == 'fireball':
                #create a fireball scroll
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, '#', 'scroll of fireball', libtcod.red, item=item_component)
            elif choice == 'confuse':
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, '#', 'scroll of confusion', libtcod.light_gray, item=item_component)
            elif choice == 'sword':
                #create a sword
                equipment_component = Equipment(slot='right hand', power_bonus=3)
                item = Object(x, y, '/', 'sword', libtcod.sky, equipment=equipment_component)
            elif choice == 'shield':
                #create a shield
                equipment_component = Equipment(slot='left hand', defense_bonus=1)
                item = Object(x,y, '[', 'shield', libtcod.darker_orange, equipment=equipment_component)
                
            objects.append(item)
            item.send_to_back() #items appear below other objects
            item.always_visible = True
            
########## Test Functions   
        
def col_test(max_iterations):
    for column in range(0,max_iterations-1):
        x = libtcod.random_get_int(0,1,MAP_WIDTH-1)
        y = libtcod.random_get_int(0,1,MAP_HEIGHT-1)
        if map[x][y].blocked == False:
            map[x][y].blocked = True
            map[x][y].block_sight = True
    

def room_test():
    room1 = Rect(20,15,10,15)
    room2 = Rect(50,15,10,15)
    create_room(room1)
    create_room(room2)
    

    
#################
#   Rendering
#################

def render_all():

    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute
    
    move_camera(player.x, player.y)
    
    if fov_recompute:
        #recomputes FOV if needed (player move, etc)
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
        libtcod.console_clear(con)
    
    #draw the map
    for y in range(CAMERA_HEIGHT):
        for x in range(CAMERA_WIDTH):
            (map_x, map_y) = (camera_x + x, camera_y + y)
            visible = libtcod.map_is_in_fov(fov_map, map_x, map_y)
            wall = map[map_x][map_y].block_sight
            if not visible:
                if map[map_x][map_y].explored:
                    if wall:
                        libtcod.console_set_char_background(con,x,y,color_dark_wall,libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
            else:
                if wall:
                    libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
                else:
                    libtcod.console_set_char_background(con,x,y,color_light_ground,libtcod.BKGND_SET)
                #since visible, explores tile
                map[map_x][map_y].explored = True
                
    #draw all objects in the list
    for object in objects:
                if object != player:
                        object.draw()
    player.draw()
        
        
    #writes "con" console to the root console
    libtcod.console_blit(con,0,0,MAP_WIDTH,MAP_HEIGHT,0,0,0)
    
    #prepare to render the GUI panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)
    
    #print the game messages, one line at a time
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1
    
    #show the player's health
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
        libtcod.light_red, libtcod.darker_red)
    #show dungeon level 
    libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon level ' + str(dungeon_level))
    
    #display names of objects under the mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
        
    #blit the contents of "panel" to root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
    
    
#########################
#   Handles keypresses
#########################

def handle_keys():
    global playerx, playery
    global fov_recompute
    global keys
    
    #key = libtcod.console_check_for_keypress()  #real time game
    #key = libtcod.console_wait_for_keypress(True) #turn-based game
    
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
        
        # Escape: exit the game
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit' #execues 'exit' in main loop
    
    if game_state == 'playing':
        #movement keys
        if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
            player_move_or_attack(0,-1)
            fov_recompute = True
        
        elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
            player_move_or_attack(0,1)
            fov_recompute = True
        
        elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1,0)
            fov_recompute = True
        
        elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
            player_move_or_attack(1,0)
            fov_recompute = True
        elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1, -1)
            fov_recompute = True
        elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
            player_move_or_attack(1, -1)
            fov_recompute = True
        elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1, 1)
            fov_recompute = True
        elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
            player_move_or_attack(1, 1)
            fov_recompute = True
        elif key.vk == libtcod.KEY_KP5:
            pass    #do nothing, letting monsters take a turn
        else:
            #test for other keys
            key_char = chr(key.c)
            
            if key_char == 'g':
                #pick up an item
                for object in objects:  #look for an item in the player's location
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break
                        
            if key_char == 'i':
                #show the inventory
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other key to exit')
                if chosen_item is not None:
                    chosen_item.use()
                    
            if key_char == 'd':
                #show the inventory, if an item is selected, drop it
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()
                    
            if key_char == '<':
        #go down stairs, if the player is on them
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()
                    
            if key_char == 'c':
            #show character info
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
            '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
            '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)

            return 'didnt-take-turn'
            
############    Initialization & Main Loop Functions

def main_menu():
    img = libtcod.image_load('menu_background1.png')
    
    while not libtcod.console_is_window_closed():
        #show the background image, at twice regular console resolution
        libtcod.image_blit_2x(img, 0, 0, 0)
        
        #show the game's title, and credits!
        libtcod.console_set_default_foreground(0, libtcod.light_yellow)
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER,
            'Generic Rogue-Like')
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER,
            'By Justin, thanks to Jotaf')

        #show options and wait for the player's choice
        choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)
        
        if choice == 0: #new game
            new_game()
            play_game()
        elif choice == 2:   #quit
            break
            
        if choice == 1: #load last game
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game()
        
def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level
    
    #creates the player
    fighter_component = Fighter(hp=PLAYER_HP, defense=PLAYER_DEFENSE, power=PLAYER_POWER, xp=0, death_function=player_death)
    player = Object(0,0,'@', 'player', libtcod.white, blocks=True, fighter=fighter_component)
    player.level = 1

    dungeon_level = 1
    #makes the map
    make_map()
    #create message list and colors, starts empty
    game_msgs = []
    #creates the inventory
    inventory = []
    
    #initializes FOV
    initialize_fov()

    game_state='playing'
    #print a welcome message!
    message('You awake to find yourself alone in a pit. Good luck, stranger.', libtcod.blue)

    #initial equipment: a dagger, rotting rags
    equipment_component = Equipment(slot='right hand', power_bonus=2)
    obj = Object(0,0, '-', 'dagger', libtcod.sky, equipment=equipment_component)
    inventory.append(obj)
    equipment_component.equip()
    obj.always_visible = True

    equipment_component = Equipment(slot='body', defense_bonus=1)
    obj = Object(0,0, '&', 'dirty rags', libtcod.Color(102, 51, 0), equipment=equipment_component)
    inventory.append(obj)
    equipment_component.equip()
    obj.always_visible = True

def initialize_fov():
        global fov_recompute, fov_map
        fov_recompute = True
    
        ######## FOV
        fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
        
        libtcod.console_clear(con)  #unexplored areas start black

def play_game():
    global camera_x, camera_y, key, mouse
            
    player_action = None
            
    #intializes controls
    mouse = libtcod.Mouse()
    key = libtcod.Key()
    
    (camera_x, camera_y) = (0,0)
    
    while not libtcod.console_is_window_closed():
    
        #checks for mouse or keypress events
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
    
        #renders the console
        render_all()
    
        #update the console
        libtcod.console_flush()
        
        #check for a level up for player
        check_level_up()
    
        #clears old position
        for object in objects:
            object.clear()
    
        #handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break

        #let monsters take their turn
        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()
                    
def save_game():
    #open a new empty shelve(possibly overwriting an old one)
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)    #index of player
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level
    file.close()
    
def load_game():
    #open the previously saved shelve and load the game data
    global map, objects, player, inventory, game_msgs, game_state, dungeon_level, stairs
    
    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level']
    file.close()
    
    initialize_fov()
    
def next_level():
    global dungeon_level

    #advance to the next level
    message('You take a moment to rest, and recover your strength', libtcod.light_violet)
    player.fighter.heal(player.fighter.max_hp/2)    #heal the player
    
    message('After a rare moment of peace, you descend deeper into the heart of the dungeon...', libtcod.red)
    dungeon_level += 1
    make_map()  #create a fresh level
    initialize_fov()
        

################################
#   Intialization and Main Loop
################################

#gets game font
libtcod.console_set_custom_font ('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)

#initializes console
libtcod.console_init_root (SCREEN_WIDTH, SCREEN_HEIGHT, 'firstrouge', False)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)    #canvas, draws to console
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT) #GUI panel

#sets framerate
libtcod.sys_set_fps(LIMIT_FPS)



######### Testing Section
#npc = Object(SCREEN_WIDTH/2 - 5, SCREEN_HEIGHT/2, '@', libtcod.yellow) ##must add to object list
#col_test(22)  #tests placing columns
#room_test()
#player.x = 25
#player.y = 23
#create_h_tunnel(25,55,23)

#XXXXXXXXXXXXXX
#   Main Loop
#XXXXXXXXXXXXXX



main_menu()
