/*

Added state potential to HUD

*/



// How long a graphics update should take in milliseconds
// Note that the server updates at 30 fps



console.log("executing graphics");
var ANIMATION_DURATION = 50;

var DIRECTION_TO_NAME = {
    '0,-1': 'NORTH',
    '0,1': 'SOUTH',
    '1,0': 'EAST',
    '-1,0': 'WEST'
};

var scene_config = {
    player_colors : {0: 'blue', 1: 'green'},
    tileSize : 80,
    animation_duration : ANIMATION_DURATION,
    show_post_cook_time : false,
    cook_time : 20,
    assets_loc : "./static/assets/",
    audio_loc : "./static/audio/",
    hud_size : 360,

};

var game_config = {
    type: Phaser.WEBGL,
    pixelArt: true,
    scale: {
        mode: Phaser.Scale.NONE},
};

var graphics;

var rangeSlider = function () {
    var slider = $('.range-slider'),
        range = $('.range-slider__range'),
        value = $('.range-slider__value');

    slider.each(function () {

        value.each(function () {
            var value = $(this).prev().attr('value');
            $(this).html(value);
        });

        range.on('input', function () {
            $(this).next(value).html(this.value);
        });
    });
};


// Invoked at every state_pong event from server
function drawState(state) {
    // Try catch necessary because state pongs can arrive before graphics manager has finished initializing
    try {
        graphics.set_state(state);
    } catch {
        console.log("error updating state");
    }
};

// Invoked at 'start_game' event déclenché par app.py, écouté par planning.js 
// qui définie graphics_config avec les paramètres de la partie
function graphics_start(graphics_config) {
    scene_config.condition = graphics_config.condition;
    scene_config.mechanic = graphics_config.mechanic;
    scene_config.Game_Trial_Timer = graphics_config.Game_Trial_Timer;
    scene_config.show_counter_drop = graphics_config.show_counter_drop;
    graphics = new GraphicsManager(game_config, scene_config, graphics_config);
};

// Invoked at 'end_game' event
function graphics_end() {
    graphics.game.renderer.destroy();
    graphics.game.loop.stop();
    graphics.game.destroy();
    
}

function graphics_reset(graphics_config) {
    let start_info = graphics_config.start_info;
    start_info.counter_goals.forEach(element => start_info.terrain[element[1]][element[0]] = 'Y');
    game_config.scene.terrain = start_info.terrain;
    game_config.scene.tileSize = 600/start_info.terrain[0].length;
    game_config.scene.start_state = start_info.state;
    game_config.scene.condition = graphics_config.condition;
    game_config.scene.scene.restart();
}

class GraphicsManager { // initialise et gère les graphismes du jeu
    constructor(game_config, scene_config, graphics_config) {
        let start_info = graphics_config.start_info;
        start_info.counter_goals.forEach(element => start_info.terrain[element[1]][element[0]] = 'Y');
        scene_config.terrain = start_info.terrain;
        scene_config.start_state = start_info.state;
        //scene_config.condition = 
        game_config.scene = new OvercookedScene(scene_config);
        game_config.width = 600 + scene_config.hud_size ;//scene_config.tileSize*scene_config.terrain[0].length + scene_config.hud_size;
        game_config.height = 600;//scene_config.tileSize*scene_config.terrain.length  //+ scene_config.hud_size;
        game_config.parent = graphics_config.container_id;
        console.log(game_config)       
        try{
            this.game = new Phaser.Game(game_config);
        }
        catch(error){
            console.log(error);
            location.reload();
        }        
    }

    set_state(state) {
        this.game.scene.getScene('PlayGame').set_state(state);
    }
}


class OvercookedScene extends Phaser.Scene { // dessine les éléments individuels du layout en utilisant Phaser
    constructor(config) {
        super({key: "PlayGame"});
        this.state = config.start_state.state;
        this.player_colors = config.player_colors;
        this.terrain = config.terrain;
        this.tileSize = 600/config.terrain[0].length//config.tileSize;
        this.animation_duration = config.animation_duration;
        this.show_post_cook_time = config.show_post_cook_time;
        this.cook_time = config.cook_time;
        this.hud_size = config.hud_size;
        this.assets_loc = config.assets_loc;
        this.audio_loc = config.audio_loc;
        this.audio = new Audio(); // Definition audio
        this.isPlaying = false; // Definition si le son est en cours de lecture
        this.soundQueueAsset = []; // Queue to manage sound asset intention
        this.soundQueueRecipe = []; // Queue to manage sound recipe intention
        this.lastIntentions = null; // Store the last intentions
        this.hud_size = config.hud_size;
        this.hud_data = {
            potential : config.start_state.potential,
            score : config.start_state.score,
            time : config.start_state.time_left,
            bonus_orders : config.start_state.state.bonus_orders,
            all_orders : config.start_state.state.all_orders,
            intentions : config.start_state.intentions
        }
        this.condition = config.condition;
        this.mechanic = config.mechanic;
        console.log(config);
        this.Game_Trial_Timer = config.Game_Trial_Timer;
        this.show_counter_drop = config.show_counter_drop;
        this.currentRecipe = null; // Property to store the current recipe
        this.lastRecipeIntentions = null;
        this.lastAssetIntentions = null;
    }

    set_state(state) {
        this.hud_data.potential = state.potential;
        this.hud_data.score = state.score;
        this.hud_data.time = Math.round(state.time_left);
        this.hud_data.bonus_orders = state.state.bonus_orders;
        this.hud_data.all_orders = state.state.all_orders;
        this.hud_data.intentions = state.intentions;
        this.state = state.state;
    }

    preload() {
        this.previous_cookingupdate_time = this.time.now
        if(!this.textures.exists("tiles")){this.load.atlas("tiles",
            this.assets_loc + "terrain.png",
            this.assets_loc + "terrain.json");}
        if(!this.textures.exists("chefs")){this.load.atlas("chefs",
            this.assets_loc + "chefs.png",
            this.assets_loc + "chefs.json");}
        if(!this.textures.exists("objects")){this.load.atlas("objects",
            this.assets_loc + "objects.png",
            this.assets_loc + "objects.json");}
        if(!this.textures.exists("soups")){this.load.multiatlas("soups",
            this.assets_loc + "soups.json",
            this.assets_loc);}
        if(!this.textures.exists("colortiles")){this.load.atlas("colortiles",
            this.assets_loc + "tiles.png",
            this.assets_loc + "tiles.json");}
        if(!this.textures.exists("types")){this.load.atlas("types",
            this.assets_loc + "types.png",
            this.assets_loc + "types.json")}

        // Pour les fichiers audio
        this.load.audio('comptoir', this.audio_loc + 'comptoir.mp3');
        this.load.audio('marmite', this.audio_loc + 'marmite.mp3');
        this.load.audio('oignon', this.audio_loc + 'oignon.mp3');
        this.load.audio('tomate', this.audio_loc + 'tomate.mp3');
        this.load.audio('assiette', this.audio_loc + 'assiette.mp3');
        this.load.audio('service', this.audio_loc + 'service.mp3');
    }

    create() {
        this.sprites = {};
        this.drawLevel();
        //this._drawState(this.state, this.sprites);
    }

    update() {
        if (typeof(this.state) !== 'undefined') {
            try {
                this._drawState(this.state, this.sprites);
            } catch (error) {
                console.log("error in drawing state")
            }
        }
        if (typeof(this.hud_data) !== 'undefined') {
            let { width, height } = this.game.canvas;
            let board_height = height ;
            let board_width = width - this.hud_size;
            this._drawHUD(this.hud_data, this.sprites, board_height, board_width, this.state);
        }
    }
    drawLevel() {
        // Fill canvas with white
        this.cameras.main.setBackgroundColor('#e6b453')
        let config = undefined
        var terrain_to_img
        //draw tiles
        if (this.show_counter_drop) {
            terrain_to_img = {
                ' ': 'floor.png',
                'X': 'counter.png',
                'P': 'pot.png',
                'O': 'onions.png',
                'T': 'tomatoes.png',
                'D': 'dishes.png',
                'S': 'serve.png',
                'Y': 'exchange.png'
            };
        } else {
            terrain_to_img = {
                ' ': 'floor.png',
                'X': 'counter.png',
                'P': 'pot.png',
                'O': 'onions.png',
                'T': 'tomatoes.png',
                'D': 'dishes.png',
                'S': 'serve.png',
                'Y': 'counter.png'
            };
        }

        let pos_dict = this.terrain;
        for (let row in pos_dict) {
            if (!pos_dict.hasOwnProperty(row)) {continue}
            for (let col = 0; col < pos_dict[row].length; col++) {
                let [x, y] = [col, row]
                let ttype = pos_dict[row][col];
                let tile = this.add.sprite(
                    this.tileSize * x,
                    this.tileSize * y,
                    "tiles",
                    terrain_to_img[ttype]
                );
                tile.setDisplaySize(this.tileSize, this.tileSize);
                tile.setOrigin(0);
            }
        }
    }
/*
    endLevel(){
        const screenCenterX = this.cameras.main.worldView.x + this.cameras.main.width / 4;
        const screenCenterY = this.cameras.main.worldView.y + this.cameras.main.height / 3;
        let n_trial_text = this.add.text(
            screenCenterX, screenCenterY, "loading next trial",
            {
                font: "70px Arial",
                fill: "black",
                align: "left"
            })
        n_trial_text.depth = 2;
        this.sprites['next_level'] = n_trial_text;
        }
*/
        
    _drawState (state, sprites) {
        sprites = typeof(sprites) === 'undefined' ? {} : sprites;

        //draw chefs
        sprites['chefs'] =
            typeof(sprites['chefs']) === 'undefined' ? {} : sprites['chefs'];
        for (let pi = 0; pi < state.players.length; pi++) {
            let chef = state.players[pi];
            let [x, y] = chef.position;
            let dir = DIRECTION_TO_NAME[chef.orientation];
            let held_obj = chef.held_object;
            if (typeof(held_obj) !== 'undefined' && held_obj !== null) {
                if (held_obj.name === 'soup') {
                    let ingredients = held_obj._ingredients.map(x => x['name']);
                    if (ingredients.includes('onion')) {
                        held_obj = "-soup-onion";
                    } else {
                        held_obj = "-soup-tomato";
                    }
                    
                }
                else {
                    held_obj = "-"+held_obj.name;
                }
            }
            else {
                held_obj = "";
            }
            
            // highlight motion goal
            if (chef.motion_goal){
                if (typeof(sprites['motion_goal']) !== 'undefined'){
                    sprites['motion_goal'].destroy();
                }
                if(this.condition.motion_goal){
                    let motion_goal = this.add.sprite(
                        this.tileSize*chef.motion_goal[0],
                        this.tileSize*chef.motion_goal[1],
                        "colortiles", "turquoise.png"
                    );
                    motion_goal.setDisplaySize(this.tileSize, this.tileSize)
                    motion_goal.setOrigin(0);
                    sprites['motion_goal'] = motion_goal
                }              
            };
            
            if (typeof(chef.intentions)!=='undefined'){
                if (typeof(sprites['recipe_goal']) !== 'undefined'){
                    sprites['recipe_goal'].destroy();
                }
                if(this.condition.recipe_head){
                    let spriteFrame = this._ingredientsToSpriteFrame(chef.intentions.recipe, "done");
                    let order_goalSprite = this.add.sprite(
                        this.tileSize*x,
                        this.tileSize*y - 40,
                        "soups",
                        spriteFrame
                    );
                    order_goalSprite.depth = 2
                    order_goalSprite.setDisplaySize(this.tileSize, this.tileSize)
                    order_goalSprite.setOrigin(0);
                    sprites['recipe_goal'] = order_goalSprite
                }              
            };
            if (typeof(sprites['chefs'][pi]) === 'undefined') {
                let chefsprite = this.add.sprite(
                    this.tileSize*x,
                    this.tileSize*y,
                    "chefs",
                    `${dir}${held_obj}.png`
                );
                chefsprite.setDisplaySize(this.tileSize, this.tileSize);
                chefsprite.depth = 1;
                chefsprite.setOrigin(0);
                let hatsprite = this.add.sprite(
                    this.tileSize*x,
                    this.tileSize*y,
                    "chefs",
                    `${dir}-${this.player_colors[pi]}hat.png`
                );
                hatsprite.setDisplaySize(this.tileSize, this.tileSize);
                hatsprite.depth = 2;
                hatsprite.setOrigin(0);
                sprites['chefs'][pi] = {chefsprite, hatsprite};
            }
            else {
                let chefsprite = sprites['chefs'][pi]['chefsprite'];
                let hatsprite = sprites['chefs'][pi]['hatsprite'];
                chefsprite.setFrame(`${dir}${held_obj}.png`);
                hatsprite.setFrame(`${dir}-${this.player_colors[pi]}hat.png`);
                this.tweens.add({
                    targets: [chefsprite, hatsprite],
                    x: this.tileSize*x,
                    y: this.tileSize*y,
                    duration: this.animation_duration,
                    ease: 'Linear',
                    onComplete: (tween, target, player) => {
                        target[0].setPosition(this.tileSize*x, this.tileSize*y);
                        //this.animating = false;
                    }
                })
            }
        }

        //draw environment objects
        if (typeof(sprites['objects']) !== 'undefined') {
            for (let objpos in sprites.objects) {
                let {objsprite, timesprite} = sprites.objects[objpos];
                objsprite.destroy();
                if (typeof(timesprite) !== 'undefined') {
                    timesprite.destroy();
                }
            }
        }
        sprites['objects'] = {};

        for (let objpos in state.objects) {
            if (!state.objects.hasOwnProperty(objpos)) { continue }
            let obj = state.objects[objpos];
            let [x, y] = obj.position;
            let terrain_type = this.terrain[y][x];
            let spriteframe;
            let soup_status;
            if ((obj.name === 'soup') && (terrain_type === 'P')) {
                let ingredients = obj._ingredients.map(x => x['name']);

                // select pot sprite
                if (!obj.is_ready) {
                    soup_status = "idle";
                }
                else {
                    soup_status = "cooked";
                }
                spriteframe = this._ingredientsToSpriteFrame(ingredients, soup_status);
                let objsprite = this.add.sprite(
                    this.tileSize*x,
                    this.tileSize*y,
                    "soups",
                    spriteframe
                );
                objsprite.setDisplaySize(this.tileSize, this.tileSize);
                objsprite.depth = 1;
                objsprite.setOrigin(0);
                let objs_here = {objsprite};

                // show time accordingly
                let show_time = true;
                if (obj._cooking_tick > obj.cook_time && !this.show_post_cook_time || obj._cooking_tick == -1) {
                    show_time = false;
                }
                if (show_time) {
                    let timesprite =  this.add.text(
                        this.tileSize*(x+.5),
                        this.tileSize*(y+.6),
                        String(obj._cooking_tick),
                        {
                            font: "25px Arial",
                            fill: "red",
                            align: "center",
                        }
                    );
                    timesprite.depth = 2;
                    objs_here['timesprite'] = timesprite;
                }

                sprites['objects'][objpos] = objs_here
            }
            else if (obj.name === 'soup') {
                let ingredients = obj._ingredients.map(x => x['name']);
                let soup_status = "done";
                spriteframe = this._ingredientsToSpriteFrame(ingredients, soup_status);
                let objsprite = this.add.sprite(
                    this.tileSize*x,
                    this.tileSize*y,
                    "soups",
                    spriteframe
                );
                objsprite.setDisplaySize(this.tileSize, this.tileSize);
                objsprite.depth = 1;
                objsprite.setOrigin(0);
                sprites['objects'][objpos] = {objsprite};
            }
            else {
                if (obj.name === 'onion') {
                    spriteframe = "onion.png";
                }
                else if (obj.name === 'tomato') {
                    spriteframe = "tomato.png";
                }
                else if (obj.name === 'dish') {
                    spriteframe = "dish.png";
                }
                let objsprite = this.add.sprite(
                    this.tileSize*x,
                    this.tileSize*y,
                    "objects",
                    spriteframe
                );
                objsprite.setDisplaySize(this.tileSize, this.tileSize);
                objsprite.depth = 1;
                objsprite.setOrigin(0);
                sprites['objects'][objpos] = {objsprite};
            }
        }        
        // Afficher et intention audio des ingrédients de la recette en cours creuser
        if (this.condition.recipe_sound) {
        // Traiter les différents ingrédients qui composent la recette
            if (typeof(state.players[0].intentions) !== 'undefined') {
                let chef = state.players[0];
                let ingredients = chef.intentions.recipe;
                this._playRecipeSounds(ingredients)/*;

                // Afficher les ingrédients qui composent la recette voulue par l'agent (vérifier la cohérence)
                let ingredients_str = ingredients.join(", ");
                if (typeof(sprites['recipe_ingredients']) !== 'undefined') {
                    sprites['recipe_ingredients'].setText("Ingredients: " + ingredients_str);
                } else {
                    sprites['recipe_ingredients'] = this.add.text(
                        this.game.config.width - this.hud_size + 5, this.game.config.height - 50,
                        "Ingredients: " + ingredients_str,
                        {
                            font: "20px Arial",
                            fill: "black",
                            align: "left"
                        }
                    );
                }*/
            }
            
        }
    }

// Jouer des sons pour les ingrédients des recettes
    _playRecipeSounds(ingredients) {
        // Ne joue le son que si la recette a changé
        let newRecipe = ingredients.join(",");
        if (this.currentRecipe === newRecipe) {
            return;
        }
        this.currentRecipe = newRecipe;

        // Génère le nom du fichier son pour la recette
        let recipeSound = this._getRecipeSoundFile(ingredients);

        // Vide la file et ajoute le son spécifique à la recette
        this.soundQueueRecipe = [];
        this.soundQueueRecipe.push(recipeSound);

        const playNextSoundRecipe = () => {
            if (this.isPlaying || this.soundQueueRecipe.length === 0) {
                return;
            }
            let soundKey = this.soundQueueRecipe.shift();
            this.audio.src = this.audio_loc + soundKey;
            this.audio.playbackRate = 1;
            this.audio.play().then(() => {
                this.isPlaying = true;
                this.audio.onended = () => {
                    this.isPlaying = false;
                    playNextSoundRecipe();
                };
            }).catch(error => {
                if (error.name !== 'AbortError') {
                    console.error("Audio play failed:", error);
                }
                this.isPlaying = false;
                playNextSoundRecipe();
            });
        };

        playNextSoundRecipe();
    }

    _getRecipeSoundFile(ingredients) {
        let num_onions = ingredients.filter(x => x === 'onion').length;
        let num_tomatoes = ingredients.filter(x => x === 'tomato').length;
        return `recette_${num_onions}o_${num_tomatoes}t.mp3`;
    }

    _drawHUD(hud_data, sprites, board_height, board_width, state) {
        if (typeof(hud_data.all_orders) !== 'undefined') {
            this._drawAllOrders(hud_data.all_orders, sprites, board_height, board_width); // affiche les recette restantes
        }
        /* if (typeof(hud_data.bonus_orders) !== 'undefined') {
            this._drawBonusOrders(hud_data.bonus_orders, sprites, board_height);
        } */
        //console.log(this.Game_Trial_Timer);
        if (typeof(hud_data.time) !== 'undefined' && this.mechanic == "recipe" && this.Game_Trial_Timer) {//changed to see what i get : that's what was intended
            //console.log("_drawTimeLeft");
            this._drawTimeLeft(hud_data.time, sprites, board_height, board_width);
            //this._validateOrder(sprites, board_height, board_width);
        }
        if (typeof(hud_data.score) !== 'undefined'&& this.mechanic !== "recipe") {
            this._drawScore(hud_data.score, sprites, board_height, board_width);
        }
        if (typeof(hud_data.potential) !== 'undefined' && hud_data.potential !== null) {
            console.log(hud_data.potential)
            this._drawPotential(hud_data.potential, sprites, board_height, board_width); // fonction inconnue
        }
        if (typeof(hud_data.intentions) !== 'undefined' && hud_data.intentions !== null) {
            // Nouvelle fonction pour séquencer les sons recette puis asset
            if (this.condition.recipe_sound && this.condition.asset_sound){
                this._playIntentionsAudioSequence(hud_data, sprites, board_height, board_width, state);
            }
            else {
                if (this.condition.recipe_sound) {
                // Traiter les différents ingrédients qui composent la recette
                    if (typeof(state.players[0].intentions) !== 'undefined') {
                        let chef = state.players[0];
                        let ingredients = chef.intentions.recipe;
                        this._playRecipeSounds(ingredients)
                    }
                }
                if (this.condition.asset_sound){
                    this._soundIntentions(hud_data.intentions.goal, sprites, board_height, board_width); // joue le son relatifs aux intentions d'assets
                }
            }
            if (this.condition.asset_hud){
                this._drawGoalIntentions(hud_data.intentions.goal, sprites, board_height, board_width); // affiche les intentions d'assets
            }                   
            //this._drawAgentType(hud_data.intentions.agent_name, sprites, board_height, board_width)   
            if (typeof(hud_data.all_orders) !== 'undefined'  && this.condition.recipe_hud ) {
                this._drawAllOrders(hud_data.all_orders, sprites, board_height, board_width, hud_data.intentions.recipe); // surligne la recette que l'agent a l'intention de faire
            }        
        }
    }

    _drawBonusOrders(orders, sprites, board_height) {
        if (typeof(orders) !== 'undefined' && orders !== null) {
            let orders_str = "Bonus Orders: ";
            if (typeof(sprites['bonus_orders']) !== 'undefined') {
                // Clear existing orders
                sprites['bonus_orders']['orders'].forEach(element => {
                    element.destroy();
                });
                sprites['bonus_orders']['orders'] = [];

                // Update with new orders
                for (let i = 0; i < orders.length; i++) {
                    let spriteFrame = this._ingredientsToSpriteFrame(orders[i]['ingredients'], "done");
                    let orderSprite = this.add.sprite(
                        130 + 40 * i,
                        board_height + 100,
                        "soups",
                        spriteFrame
                    );
                    sprites['bonus_orders']['orders'].push(orderSprite);
                    orderSprite.setDisplaySize(60, 60);
                    orderSprite.setOrigin(0);
                    orderSprite.depth = 1;
                }
            }
            else {
                sprites['bonus_orders'] = {};
                sprites['bonus_orders']['str'] = this.add.text(
                    5, board_height + 120, orders_str,
                    {
                        font: "20px Arial",
                        fill: "red",
                        align: "left"
                    }
                )
                sprites['bonus_orders']['orders'] = []
            }
        }
    }

    _drawAllOrders(orders, sprites, board_height, board_width, intentions) {
        if (typeof(orders) !== 'undefined' && orders !== null) {
            let orders_str = "All Orders: ";
            if (typeof(sprites['all_orders']) !== 'undefined') {
                // Clear existing orders
                sprites['all_orders']['orders'].forEach(element => {
                    element.destroy();
                });
                sprites['all_orders']['orders'] = [];

                // Update with new orders
                for (let i = 0; i < orders.length; i++) {
                    if (JSON.stringify(orders[i]['ingredients']) === JSON.stringify(intentions)){     
                        let highlightSprite = this.add.sprite(
                            board_width +10 + 40 * i,
                            50,
                            "colortiles",
                            "turquoise.png"    
                        );
                        highlightSprite.setDisplaySize(40,40);
                        highlightSprite.setOrigin(0);
                        highlightSprite.depth = 0;
                        sprites['all_orders']['orders'].push(highlightSprite);
                    }
                    let spriteFrame = this._ingredientsToSpriteFrame(orders[i]['ingredients'], "done");
                    let orderSprite = this.add.sprite(
                        board_width + 40 * i,
                        40,
                        "soups",
                        spriteFrame
                    );
                    sprites['all_orders']['orders'].push(orderSprite);
                    orderSprite.setDisplaySize(60, 60);
                    orderSprite.setOrigin(0);
                    orderSprite.depth = 1;
                }
            }
            else {
                sprites['all_orders'] = {};
                sprites['all_orders']['str'] = this.add.text(
                    board_width + 5, 15 , orders_str,
                    {
                        font: "20px Arial",
                        fill: "red",
                        align: "left"
                    }
                )
                sprites['all_orders']['orders'] = []
            }
        }
    }

// Ajout de la fonction permettant de jouer le son des intentions (objectif de l'agent en terme d'asset)
    _soundIntentions(intentions, sprites, board_height, board_width) {
        const terrain_to_sound = {
            ' ': '',
            'X': 'comptoir',
            //'P': 'marmite',
            'O': 'oignon',
            'T': 'tomate',
            'D': 'assiette',
            'S': 'service'
        };

        if (typeof(intentions) !== 'undefined' && intentions !== null) {
            // Check if intentions have changed
            if (JSON.stringify(intentions) === JSON.stringify(this.lastIntentions)) {
                return; // Do not play sound if intentions have not changed
            }

            // Update last intentions
            this.lastIntentions = intentions;

            // Clear the sound queue before adding new sounds
            this.soundQueueAsset = [];
            //console.log("Intentions:", intentions); // Log the intentions

            // Update with new sounds
            for (let i = 0; i < intentions.length; i++) {
                let soundKey = terrain_to_sound[intentions[i]];
                if (soundKey) {
                    this.soundQueueAsset.push(soundKey);
                    //console.log("taille sound queue add", this.soundQueueAsset.length);
                    //console.log("Added sound to queue:", soundKey); // Log the added sound
                }
            }

            const playNextSoundAsset = () => {
                if (this.soundQueueAsset.length === 0) {
                    this.isPlaying = false;
                    //console.log("Sound queue is empty, stopping playback."); // Log when the queue is empty
                    return;
                }
                let soundKey = this.soundQueueAsset.shift();
                //console.log("valeur soundKey apres remove liste", soundKey);
                //console.log("taille sound queue remove", this.soundQueueAsset.length);
                let sound = this.sound.add(soundKey);
                sound.setRate(1);
                sound.setVolume(1.0);
                //console.log("Playing sound:", soundKey); // Log the sound being played

                sound.play();
                sound.once('complete', () => {
                    this.isPlaying = false;
                    //console.log("Audio play ended"); // Log when audio play ends
                    playNextSoundAsset();
                });
            };

            // Start playing the first sound if not already playing
            if (!this.isPlaying) {
                playNextSoundAsset();
            }
        }
    }

    _drawGoalIntentions(intentions, sprites, board_height, board_width) {
        let terrain_to_img = {
            ' ': 'floor.png',
            'X': 'counter.png',
            'P': 'pot.png',
            'O': 'onions.png',
            'T': 'tomatoes.png',
            'D': 'dishes.png',
            'S': 'serve.png'
        };
        if (typeof(intentions) !== 'undefined' && intentions !== null) {
            let intentions_str = "Partner's intentions:  ";
            if (typeof(sprites['intentions']) !== 'undefined') {
                // Clear existing orders
                sprites['intentions'].forEach(element => {
                    element.destroy();
                });
                sprites['intentions'] = [];

                // Update with new orders
                for (let i = 0; i < intentions.length; i++) {
                    let spriteFrame = terrain_to_img[intentions[i]];
                    let orderSprite = this.add.sprite(
                        board_width +10 + this.tileSize * i,
                        140,
                        "tiles",
                        spriteFrame
                    );
                    sprites['intentions'].push(orderSprite);
                    orderSprite.setDisplaySize(60, 60);
                    orderSprite.setOrigin(0);
                    orderSprite.depth = 1;
                }
            }
            else {
                sprites['intentions'] = {};
                sprites['intentions']['str'] = this.add.text(
                    board_width + 10, 100, intentions_str,
                    {
                        font: "20px Arial",
                        fill: "red",
                        align: "left"
                    }
                )
                sprites['intentions'] = []
            }
        }
    }

    _drawAgentType(agent_type, sprites, board_height, board_width) {
        let type_to_img = {
            'rational': 'rational.png',
            'greedy': 'greedy.png',
            'lazy': 'lazy.png'
        };
        let intentions_str = "Agent type:  ";
        if (typeof (sprites['type']) !== 'undefined') {
            // Clear existing orders
            sprites['type'].forEach(element => {
                element.destroy();
            });
            sprites['type'] = [];

            // Update with new orders

            let spriteFrame = type_to_img[agent_type];
            let typeSprite = this.add.sprite(
                board_width + 40 + this.tileSize,
                140,
                "types",
                spriteFrame
            );
            sprites['type'].push(typeSprite);
            typeSprite.setDisplaySize(60, 60);
            typeSprite.setOrigin(0);
            typeSprite.depth = 1;

        }
        else {
            sprites['type'] = {};
            sprites['type'] = []
        }

    }

    _drawScore(score, sprites, board_height, board_width) {
        score = "Score: "+score;
        if (typeof(sprites['score']) !== 'undefined') {
            sprites['score'].setText(score);
        }
        else {
            sprites['score'] = this.add.text(
                board_width + 5, 250, score,
                {
                    font: "20px Arial",
                    fill: "red",
                    align: "left"
                }
            )
        }
    }

    _drawPotential(potential, sprites, board_height) {
        potential = "Potential: "+potential;
        if (typeof(sprites['potential']) !== 'undefined') {
            sprites['potential'].setText(potential);
        }
        else {
            sprites['potential'] = this.add.text(
                100, board_height + 90, potential,
                {
                    font: "20px Arial",
                    fill: "red",
                    align: "left"
                }
            )
        }
    }

    _drawTimeLeft(time_left, sprites, board_height, board_width) {
        time_left = "Time Left: "+time_left;
        //console.log(time_left);
        if (typeof(sprites['time_left']) !== 'undefined') {
            sprites['time_left'].setText(time_left);
        }
        else {
            sprites['time_left'] = this.add.text(
                board_width + 5, 300, time_left,
                {
                    font: "20px Arial",
                    fill: "red",
                    align: "left"
                }
            )
        }
    }

    _validateOrder(sprites, board_height, board_width) {       
        //TODO: add the validation of the recipe 1st see(overcooked_mdp:633) 

        let valid_order = ' '
        sprites['valid_order'] = this.add.text(
            board_width + 5, 350, valid_order,
            {
                font: "20px Arial",
                fill: "red",
                align: "left"
            }
        )
    }
    

    _ingredientsToSpriteFrame(ingredients, status) {
        let num_tomatoes = ingredients.filter(x => x === 'tomato').length;
        let num_onions = ingredients.filter(x => x === 'onion').length;
        return `soup_${status}_tomato_${num_tomatoes}_onion_${num_onions}.png`
    }

    /**
     * Joue la séquence audio : annonce_recette.mp3, son de recette, puis intentions d'assets.
     * Si l'intention de recette change, recommence la séquence.
     */
    _playIntentionsAudioSequence(hud_data, sprites, board_height, board_width, state) {
        // Empêche de relancer la séquence si elle est déjà en cours
        if (this.isPlaying) return;

        // Récupère l'intention de recette courante
        let chef = state.players[0];
        let ingredients = chef && chef.intentions ? chef.intentions.recipe : [];
        let currentRecipe = ingredients.join(",");

        // Récupère les intentions d'assets courantes
        let assetIntentions = hud_data.intentions && hud_data.intentions.goal ? [...hud_data.intentions.goal] : [];

        // Si la recette n'a pas changé, ne relance pas la séquence (mais continue à jouer les intentions d'assets si besoin)
        if (this.lastRecipeIntentions === currentRecipe) {
            // On ne joue les intentions d'assets que si la séquence annonce+recette a déjà été jouée
            if (JSON.stringify(assetIntentions) !== JSON.stringify(this.lastAssetIntentions)) {
                this._playAssetIntentionsSounds(assetIntentions, sprites, board_height, board_width);
                this.lastAssetIntentions = [...assetIntentions];
            }
            return;
        }

        // Mise à jour de la dernière recette et des intentions d'assets
        this.lastRecipeIntentions = currentRecipe;
        this.lastAssetIntentions = [...assetIntentions];

        // 1. Joue annonce_recette.mp3
        this.isPlaying = true;
        this.audio.src = this.audio_loc + "annonce_recette.mp3";
        this.audio.playbackRate = 1;
        this.audio.play().then(() => {
            this.audio.onended = () => {
                // 2. Joue le son de la recette complète
                if (ingredients.length > 0) {
                    let recipeSound = this._getRecipeSoundFile(ingredients);
                    this.audio.src = this.audio_loc + recipeSound;
                    this.audio.playbackRate = 1;
                    this.audio.play().then(() => {
                        this.audio.onended = () => {
                            this.isPlaying = false;
                            // 3. Joue les intentions d'assets successives
                            if (assetIntentions.length > 0) {
                                this._playAssetIntentionsSounds(assetIntentions, sprites, board_height, board_width);
                            }
                        };
                    }).catch(error => {
                        this.isPlaying = false;
                        if (assetIntentions.length > 0) {
                            this._playAssetIntentionsSounds(assetIntentions, sprites, board_height, board_width);
                        }
                    });
                } else {
                    this.isPlaying = false;
                    if (assetIntentions.length > 0) {
                        this._playAssetIntentionsSounds(assetIntentions, sprites, board_height, board_width);
                    }
                }
            };
        }).catch(error => {
            this.isPlaying = false;
            // Si erreur sur annonce, on tente quand même la suite
            if (ingredients.length > 0) {
                let recipeSound = this._getRecipeSoundFile(ingredients);
                this.audio.src = this.audio_loc + recipeSound;
                this.audio.playbackRate = 1;
                this.audio.play().then(() => {
                    this.audio.onended = () => {
                        this.isPlaying = false;
                        if (assetIntentions.length > 0) {
                            this._playAssetIntentionsSounds(assetIntentions, sprites, board_height, board_width);
                        }
                    };
                }).catch(() => {
                    this.isPlaying = false;
                    if (assetIntentions.length > 0) {
                        this._playAssetIntentionsSounds(assetIntentions, sprites, board_height, board_width);
                    }
                });
            } else {
                if (assetIntentions.length > 0) {
                    this._playAssetIntentionsSounds(assetIntentions, sprites, board_height, board_width);
                }
            }
        });
    }

    /**
     * Joue les sons correspondant à la séquence d'intentions d'assets.
     * Cette fonction ne relance la séquence que si la recette n'a pas changé.
     */
    _playAssetIntentionsSounds(intentions, sprites, board_height, board_width) {
    const terrain_to_sound = {
        ' ': '',
        'X': 'comptoir',
        //'P': 'marmite',
        'O': 'oignon',
        'T': 'tomate',
        'D': 'assiette',
        'S': 'service'
    };
    // vérifie que intention n'est ni nulle ni vide
    if (!intentions || intentions.length === 0) return;

    // Met à jour immédiatement la référence des intentions d'asset
    this.lastAssetIntentions = [...intentions];

    // Vide la file d'attente pour ne jouer que les intentions actuelles
    this.soundQueueAsset = [];
    for (let i = 0; i < intentions.length; i++) {
        let soundKey = terrain_to_sound[intentions[i]];
        if (soundKey) {
            this.soundQueueAsset.push(soundKey);
        }
    }
    const playNextSoundAsset = () => {
        if (this.soundQueueAsset.length === 0) {
            this.isPlaying = false;
            return;
        }
        let soundKey = this.soundQueueAsset.shift();
        let sound = this.sound.add(soundKey);
        sound.setRate(1);
        sound.setVolume(1.0);
        this.isPlaying = true;
        sound.play();
        sound.once('complete', () => {
            this.isPlaying = false;
            playNextSoundAsset();
        });
    };
    playNextSoundAsset();
}
}