/*

Added state potential to HUD

*/



// How long a graphics update should take in milliseconds
// Note that the server updates at 30 fps



// console.log("executing graphics");
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
    //scene_config.player_colors = graphics_config.player_colors;
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

    // Clear audio intention queues and history at end of current trial
    const scene = graphics.game.scene.getScene('PlayGame');
    scene.soundQueueAsset = [];
    scene.soundQueueRecipe = [];
    scene.lastAssetIntentions = null;
    scene.lastRecipeIntentions = null;
    scene.lastIntentions = null;
    scene.currentRecipe = null;
    
    // Stop all audio
    if (scene.stopAllAudio) {
        scene.stopAllAudio();
    }

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
        // console.log(game_config)       
        try{
            this.game = new Phaser.Game(game_config);
        }
        catch(error){
            // console.log(error);
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
        
        // WebAudio API setup
        this.audioContext = null;
        this.audioBuffers = new Map(); // Cache pour les buffers audio
        this.audioSources = []; // Track active audio sources
        this.isPlaying = false;
        this.isPlayingRecipe = false;
        this.isPlayingAsset = false;
        this.audioUnlockHandler = null;
        this.audioUnlockEvents = ['pointerdown', 'touchstart', 'mousedown', 'click', 'keydown', 'keyup'];
        
        // Audio control parameters
        this.audioEnabled = true; // Global audio control
        this.recipeAudioEnabled = true; // Recipe audio control
        this.assetAudioEnabled = true; // Asset audio control
        
        // Queue management
        this.soundQueueAsset = [];
        this.soundQueueRecipe = [];
        this.lastIntentions = null;
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
        // console.log(config);
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

        // Pour les fichiers audio - Preload all audio files
        const audioFiles = [
            'comptoir.mp3', 'marmite.mp3', 'oignon.mp3', 'tomate.mp3', 
            'assiette.mp3', 'service.mp3', 'annonce_recette.mp3',
            'recette_0o_1t.mp3', 'recette_0o_2t.mp3', 'recette_0o_3t.mp3',
            'recette_1o_0t.mp3', 'recette_1o_1t.mp3', 'recette_1o_2t.mp3',
            'recette_2o_0t.mp3', 'recette_2o_1t.mp3', 'recette_3o_0t.mp3'
        ];
        
        audioFiles.forEach(filename => {
            const audioKey = filename.replace('.mp3', '');
            
            // Ajouter une vérification de chargement
            this.load.audio(audioKey, this.audio_loc + filename);
            
            // Ajouter un event listener pour détecter les erreurs de chargement
            this.load.on('fileerror', (key) => {
                if (key === audioKey) {
                    // console.warn(`Failed to load audio file: ${filename}`);
                }
            });
        });
    }

    create() {
        // Initialize basic scene elements first
        this.sprites = {};
        this.drawLevel();
        this.events.once('shutdown', () => this.teardownAudioUnlockListeners());
        this.events.once('destroy', () => this.teardownAudioUnlockListeners());
        
        // Initialize WebAudio context and wait for buffers to load
        this.initializeAudioContext().then(() => {
            // console.log('Audio system fully initialized - game ready');
            // Émettre un événement pour signaler que l'audio est prêt
            this.events.emit('audio-ready');
        }).catch((error) => {
            // console.warn('Audio initialization failed, using Phaser fallback:', error);
            this.events.emit('audio-ready'); // Continuer même en cas d'erreur
        });
        
        // Debug audio system après initialisation (en mode développement uniquement)
        setTimeout(() => {
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                this.debugAudioSystem();
            }
        }, 1500); // Délai légèrement augmenté pour permettre l'initialisation async
        
        //this._drawState(this.state, this.sprites);
    }
    
    /**
     * Initialize WebAudio context and load audio buffers
     */
    async initializeAudioContext() {
        try {
            // Créer le contexte audio avec gestion de l'autoplay policy
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.setupAudioUnlockListeners();
            this.tryResumeAudioContext();
            
            // Essayer d'abord la méthode principale
            await this.loadAudioBuffers();
            
            // Si peu de buffers ont été chargés, essayer la méthode alternative
            if (this.audioBuffers.size < 5) {
                // console.log('Primary loading method failed, trying alternative...');
                await this.loadAudioBuffersAlternative();
            }
            
            // console.log('WebAudio API initialized successfully');
        } catch (error) {
            // console.warn('WebAudio API not supported or failed to initialize, falling back to Phaser Audio:', error);
            this.teardownAudioUnlockListeners();
            this.audioContext = null;
        }
    }
    
    setupAudioUnlockListeners() {
        if (this.audioUnlockHandler) {
            return;
        }

        const handler = () => {
            this.tryResumeAudioContext();
            const contextUnlocked = !this.audioContext || this.audioContext.state !== 'suspended';
            const phaserContext = this.sound && this.sound.context ? this.sound.context : null;
            const phaserUnlocked = !(phaserContext && phaserContext.state === 'suspended');

            if (contextUnlocked && phaserUnlocked) {
                this.teardownAudioUnlockListeners();
            }
        };

        this.audioUnlockHandler = handler;
        this.audioUnlockEvents.forEach(evt => {
            window.addEventListener(evt, handler, { passive: true });
        });
    }

    teardownAudioUnlockListeners() {
        if (!this.audioUnlockHandler) {
            return;
        }

        this.audioUnlockEvents.forEach(evt => {
            window.removeEventListener(evt, this.audioUnlockHandler);
        });
        this.audioUnlockHandler = null;
    }

    tryResumeAudioContext() {
        if (this.audioContext && this.audioContext.state === 'suspended') {
            this.audioContext.resume().catch(() => {});
        }

        if (this.sound && this.sound.context && this.sound.context.state === 'suspended') {
            try {
                this.sound.unlock();
            } catch (e) {
                // Ignore errors from unlock attempts
            }
        }
    }

    /**
     * Load all audio files into buffers for WebAudio API
     */
    async loadAudioBuffers() {
        const audioFiles = [
            'comptoir', 'marmite', 'oignon', 'tomate', 
            'assiette', 'service', 'annonce_recette',
            'recette_0o_1t', 'recette_0o_2t', 'recette_0o_3t',
            'recette_1o_0t', 'recette_1o_1t', 'recette_1o_2t',
            'recette_2o_0t', 'recette_2o_1t', 'recette_3o_0t'
        ];
        
        // Attendre que Phaser ait fini de charger tous les fichiers audio
        await new Promise((resolve) => {
            if (this.load.isLoading()) {
                this.load.once('complete', resolve);
            } else {
                resolve();
            }
        });
        
        for (const audioKey of audioFiles) {
            try {
                // Vérifier si le cache audio existe et contient le fichier
                if (this.cache.audio.exists(audioKey)) {
                    // Essayer de récupérer l'ArrayBuffer directement via fetch
                    try {
                        const response = await fetch(this.audio_loc + audioKey + '.mp3');
                        const arrayBuffer = await response.arrayBuffer();
                        const decodedBuffer = await this.audioContext.decodeAudioData(arrayBuffer.slice());
                        this.audioBuffers.set(audioKey, decodedBuffer);
                        // console.log(`Successfully loaded audio buffer for ${audioKey}`);
                    } catch (fetchError) {
                        // console.warn(`Direct fetch failed for ${audioKey}, trying Phaser cache:`, fetchError);
                        
                        // Fallback: essayer d'accéder aux données Phaser
                        const audioBuffer = this.cache.audio.get(audioKey);
                        if (audioBuffer && audioBuffer.data) {
                            const decodedBuffer = await this.audioContext.decodeAudioData(audioBuffer.data.slice());
                            this.audioBuffers.set(audioKey, decodedBuffer);
                            // console.log(`Successfully loaded audio buffer from Phaser cache for ${audioKey}`);
                        } else {
                            // console.warn(`Audio buffer data missing for ${audioKey}, will use Phaser fallback`);
                        }
                    }
                } else {
                    // console.warn(`Audio file ${audioKey} not found in cache, will use Phaser fallback`);
                }
            } catch (error) {
                // console.warn(`Failed to load audio buffer for ${audioKey}:`, error, 'Will use Phaser fallback');
            }
        }
        
        // console.log(`WebAudio buffers loaded: ${this.audioBuffers.size}/${audioFiles.length}`);
    }
    
    /**
     * Alternative method to load audio buffers more aggressively
     */
    async loadAudioBuffersAlternative() {
        const audioFiles = [
            'comptoir', 'marmite', 'oignon', 'tomate', 
            'assiette', 'service', 'annonce_recette',
            'recette_0o_1t', 'recette_0o_2t', 'recette_0o_3t',
            'recette_1o_0t', 'recette_1o_1t', 'recette_1o_2t',
            'recette_2o_0t', 'recette_2o_1t', 'recette_3o_0t'
        ];
        
        // console.log('Loading audio buffers using alternative method...');
        
        const promises = audioFiles.map(async (audioKey) => {
            try {
                const response = await fetch(this.audio_loc + audioKey + '.mp3');
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const arrayBuffer = await response.arrayBuffer();
                const decodedBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
                this.audioBuffers.set(audioKey, decodedBuffer);
                // console.log(`✓ Loaded ${audioKey} via fetch`);
                return true;
            } catch (error) {
                // console.warn(`✗ Failed to load ${audioKey} via fetch:`, error);
                return false;
            }
        });
        
        await Promise.allSettled(promises);
        // console.log(`Alternative method: ${this.audioBuffers.size}/${audioFiles.length} buffers loaded`);
    }
    
    /**
     * Play audio using WebAudio API or fallback to Phaser audio
     */
    playAudio(audioKey, playbackRate = 1, volume = 1.0, onComplete = null) {
        if (!this.audioEnabled) {
            if (onComplete) onComplete();
            return;
        }

        this.tryResumeAudioContext();
        
        // Pour les sons critiques (recettes), essayer d'attendre un court délai si les buffers ne sont pas prêts
        if ((audioKey.startsWith('recette_') || audioKey === 'annonce_recette') && !this.isAudioReady()) {
            // Attendre maximum 500ms pour que l'audio soit prêt
            this.waitForAudioReady(500).then(() => {
                this._playAudioInternal(audioKey, playbackRate, volume, onComplete);
            });
            return;
        }
        
        // Jouer immédiatement
        this._playAudioInternal(audioKey, playbackRate, volume, onComplete);
    }
    
    /**
     * Internal method to play audio (synchronous)
     */
    _playAudioInternal(audioKey, playbackRate, volume, onComplete) {
        if (this.audioContext && this.audioBuffers.has(audioKey)) {
            return this.playWebAudio(audioKey, playbackRate, volume, onComplete);
        } else {
            return this.playPhaserAudio(audioKey, playbackRate, volume, onComplete);
        }
    }
    
    /**
     * Play audio using WebAudio API
     */
    playWebAudio(audioKey, playbackRate, volume, onComplete) {
        try {
            // Vérifier l'état du contexte audio
            if (this.audioContext.state === 'suspended') {
                // console.log('AudioContext suspended, resuming...');
                this.audioContext.resume().then(() => {
                    this.playWebAudio(audioKey, playbackRate, volume, onComplete);
                }).catch(() => {
                    // console.warn('Failed to resume AudioContext, falling back to Phaser audio');
                    this.playPhaserAudio(audioKey, playbackRate, volume, onComplete);
                });
                return;
            }
            
            if (!this.audioBuffers.has(audioKey)) {
                // console.warn(`Audio buffer not found for ${audioKey}, falling back to Phaser audio`);
                return this.playPhaserAudio(audioKey, playbackRate, volume, onComplete);
            }
            
            const source = this.audioContext.createBufferSource();
            const gainNode = this.audioContext.createGain();
            
            source.buffer = this.audioBuffers.get(audioKey);
            source.playbackRate.value = playbackRate;
            gainNode.gain.value = volume;
            
            source.connect(gainNode);
            gainNode.connect(this.audioContext.destination);
            
            source.onended = () => {
                this.audioSources = this.audioSources.filter(s => s !== source);
                if (onComplete) onComplete();
            };
            
            this.audioSources.push(source);
            source.start();
            
            return source;
        } catch (error) {
            // console.warn('WebAudio playback failed, falling back to Phaser audio:', error);
            return this.playPhaserAudio(audioKey, playbackRate, volume, onComplete);
        }
    }
    
    /**
     * Play audio using Phaser audio system (fallback)
     */
    playPhaserAudio(audioKey, playbackRate, volume, onComplete) {
        try {
            const sound = this.sound.add(audioKey);
            sound.setRate(playbackRate);
            sound.setVolume(volume);
            
            if (onComplete) {
                sound.once('complete', onComplete);
            }
            
            sound.play();
            return sound;
        } catch (error) {
            // console.warn('Phaser audio playback failed:', error);
            if (onComplete) onComplete();
            return null;
        }
    }
    
    /**
     * Stop all playing audio
     */
    stopAllAudio() {
        // Stop WebAudio sources
        this.audioSources.forEach(source => {
            try {
                source.stop();
            } catch (e) {
                // Source may already be stopped
            }
        });
        this.audioSources = [];
        
        // Stop Phaser sounds
        this.sound.stopAll();
        
        this.isPlaying = false;
        this.isPlayingRecipe = false;
        this.isPlayingAsset = false;
    }
    
    /**
     * Set audio enable/disable states
     */
    setAudioEnabled(enabled) {
        this.audioEnabled = enabled;
        if (!enabled) {
            this.stopAllAudio();
        }
    }
    
    setRecipeAudioEnabled(enabled) {
        this.recipeAudioEnabled = enabled;
        if (!enabled && this.isPlayingRecipe) {
            this.stopAllAudio();
        }
    }
    
    setAssetAudioEnabled(enabled) {
        this.assetAudioEnabled = enabled;
        if (!enabled && this.isPlayingAsset) {
            this.stopAllAudio();
        }
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
                    if(this.condition.visual_bubbles && this.hud_data) {
                        // Mode EVH : bulles visuelles avec durées (seulement si hud_data disponible)
                        this._displayVisualBubbles(chef, sprites, x, y, this.hud_data);
                    } else if (!this.condition.visual_bubbles) {
                        // Mode recipe_head classique permanent
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
        // Note: Les sons de recettes sont maintenant gérés dans _drawHUD pour éviter les doublons
        // quand recipe_sound et asset_sound sont tous les deux activés
    }

// Jouer des sons pour les ingrédients des recettes
    _playRecipeSounds(ingredients) {
        if (!this.recipeAudioEnabled || !this.audioEnabled) {
            return;
        }
        
        // Ne joue le son que si la recette a changé
        let newRecipe = ingredients.join(",");
        if (this.currentRecipe === newRecipe) {
            return;
        }
        this.currentRecipe = newRecipe;

        // Lecture de l'annonce "prochaine recette" avant le son de recette
        const recipeSound = this._getRecipeSoundFile(ingredients);
        
        const playRecipeSound = () => {
            if (!this.recipeAudioEnabled || !this.audioEnabled || !recipeSound) {
                this.isPlayingRecipe = false;
                return;
            }
            
            this.playAudio(recipeSound.replace('.mp3', ''), 1, 1.0, () => {
                this.isPlayingRecipe = false;
            });
        };
        
        // 1. Joue l'annonce de recette
        this.isPlayingRecipe = true;
        this.playAudio('annonce_recette', 1, 1.0, () => {
            // 2. Joue ensuite le son de recette
            playRecipeSound();
        });
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
            // console.log(hud_data.potential)
            this._drawPotential(hud_data.potential, sprites, board_height, board_width); // fonction inconnue
        }
        if (typeof(hud_data.intentions) !== 'undefined' && hud_data.intentions !== null) {
            // Gestion centralisée des intentions audio pour éviter les doublons
            if (this.condition.recipe_sound && this.condition.asset_sound){
                // Cas 1: Sons de recettes ET d'assets - séquence complète
                this._playIntentionsAudioSequence(hud_data, sprites, board_height, board_width, state);
            }
            else if (this.condition.recipe_sound && !this.condition.asset_sound) {
                // Cas 2: Sons de recettes uniquement
                if (typeof(state.players[0].intentions) !== 'undefined') {
                    let chef = state.players[0];
                    let ingredients = chef.intentions.recipe;
                    this._playRecipeSounds(ingredients)
                }
            }
            else if (!this.condition.recipe_sound && this.condition.asset_sound) {
                // Cas 3: Sons d'assets uniquement
                this._soundIntentions(hud_data.intentions.goal, sprites, board_height, board_width);
            }
            // Cas 4: Aucun son (recipe_sound=false, asset_sound=false) - rien à faire
            
            // Affichage HUD (indépendant des sons)
            if (this.condition.asset_hud){
                this._drawGoalIntentions(hud_data.intentions.goal, sprites, board_height, board_width);
            }                   
            if (typeof(hud_data.all_orders) !== 'undefined' && this.condition.recipe_hud) {
                this._drawAllOrders(hud_data.all_orders, sprites, board_height, board_width, hud_data.intentions.recipe);
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
        if (!this.assetAudioEnabled || !this.audioEnabled) {
            return;
        }
        
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

            // Update with new sounds
            for (let i = 0; i < intentions.length; i++) {
                let soundKey = terrain_to_sound[intentions[i]];
                if (soundKey) {
                    this.soundQueueAsset.push(soundKey);
                }
            }

            // Play sounds from queue
            this.playAssetSoundsFromQueue();
        }
    }
    
    /**
     * Play asset sounds from queue using WebAudio API
     */
    playAssetSoundsFromQueue() {
        if (!this.assetAudioEnabled || !this.audioEnabled || this.soundQueueAsset.length === 0) {
            this.isPlayingAsset = false;
            return;
        }
        
        this.isPlayingAsset = true;
        
        const playNextSound = () => {
            if (this.soundQueueAsset.length === 0) {
                this.isPlayingAsset = false;
                return;
            }
            
            const soundKey = this.soundQueueAsset.shift();
            this.playAudio(soundKey, 1, 1.0, () => {
                playNextSound();
            });
        };
        
        playNextSound();
    }
    
    /**
     * Check if audio system is fully ready
     */
    isAudioReady() {
        return this.audioBuffers && this.audioBuffers.size > 0;
    }
    
    /**
     * Wait for audio system to be ready
     */
    waitForAudioReady(maxWaitMs = 500) {
        return new Promise((resolve) => {
            if (this.isAudioReady()) {
                resolve();
                return;
            }
            
            // Listen for audio-ready event
            const onReady = () => {
                clearTimeout(timeoutId);
                resolve();
            };
            
            this.events.once('audio-ready', onReady);
            
            // Fallback timeout - beaucoup plus court
            const timeoutId = setTimeout(() => {
                // console.warn(`Audio ready timeout reached after ${maxWaitMs}ms, proceeding with Phaser fallback`);
                this.events.off('audio-ready', onReady);
                resolve();
            }, maxWaitMs);
        });
    }

    _drawGoalIntentions(intentions, sprites, board_height, board_width) {
        let terrain_to_img = {
            ' ': 'floor.png',
            'X': 'counter.png',
            //'P': 'pot.png',
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
        time_left = "Time Left : "+time_left+" s";
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
        if (!this.recipeAudioEnabled || !this.assetAudioEnabled || !this.audioEnabled) {
            return;
        }
        
        // Empêche de relancer la séquence si elle est déjà en cours
        if (this.isPlayingRecipe || this.isPlayingAsset) return;

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
        this.isPlayingRecipe = true;
        this.playAudio('annonce_recette', 1.0, 1.0, () => {
            // 2. Joue le son de la recette complète
            if (ingredients.length > 0) {
                let recipeSound = this._getRecipeSoundFile(ingredients);
                let recipeSoundKey = recipeSound.replace('.mp3', '');
                this.playAudio(recipeSoundKey, 1, 1.0, () => {
                    this.isPlayingRecipe = false;
                    // 3. Joue les intentions d'assets successives
                    if (assetIntentions.length > 0) {
                        this._playAssetIntentionsSounds(assetIntentions, sprites, board_height, board_width);
                    }
                });
            } else {
                this.isPlayingRecipe = false;
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
        if (!this.assetAudioEnabled || !this.audioEnabled) {
            return;
        }
        
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
        
        // Play sounds from queue using WebAudio API
        this.playAssetSoundsFromQueue();
    }

    /**
     * Debug method to check audio system status
     */
    debugAudioSystem() {
        console.group('Audio System Debug');
        // console.log('Audio enabled:', this.audioEnabled);
        // console.log('Recipe audio enabled:', this.recipeAudioEnabled);
        // console.log('Asset audio enabled:', this.assetAudioEnabled);
        // console.log('WebAudio context:', this.audioContext ? this.audioContext.state : 'null');
        // console.log('Audio buffers loaded:', this.audioBuffers.size);
        // console.log('Available audio buffers:', Array.from(this.audioBuffers.keys()));
        
        // Vérifier les fichiers dans le cache Phaser
        const audioFiles = [
            'comptoir', 'marmite', 'oignon', 'tomate', 
            'assiette', 'service', 'annonce_recette',
            'recette_0o_1t', 'recette_0o_2t', 'recette_0o_3t',
            'recette_1o_0t', 'recette_1o_1t', 'recette_1o_2t',
            'recette_2o_0t', 'recette_2o_1t', 'recette_3o_0t'
        ];
        
        console.log('Phaser audio cache status:');
        audioFiles.forEach(key => {
            const exists = this.cache.audio.exists(key);
            const buffer = exists ? this.cache.audio.get(key) : null;
            // console.log(`  ${key}: exists=${exists}, hasBuffer=${buffer && buffer.buffer ? true : false}`);
        });
        
        console.groupEnd();
    }

    /**
     * Display visual bubbles for EVH condition
     */
    _displayVisualBubbles(chef, sprites, x, y, hud_data) {
        // Vérifications de sécurité
        if (!chef || !chef.intentions || !hud_data || !this.condition) {
            return;
        }
        
        // Initialiser les variables de bulle si nécessaire
        if (!this.bubbleSequence) {
            this.bubbleSequence = [];
            this.currentBubbleIndex = 0;
            this.bubbleTimer = null;
            this.currentBubbleSprite = null;
            this.currentBubbleBackground = null;  // Pour le fond blanc des assets
            this.lastRecipe = null;        // Séparer le tracking de la recette
            this.lastAssets = null;        // Séparer le tracking des assets
        }

        // Récupérer les intentions actuelles avec vérifications
        let currentRecipe = (chef.intentions && chef.intentions.recipe) ? chef.intentions.recipe : [];
        let currentAssets = (hud_data.intentions && hud_data.intentions.goal) ? [...hud_data.intentions.goal] : [];
        
        // Créer des identifiants séparés pour recette et assets
        let recipeId = JSON.stringify(currentRecipe);
        let assetsId = JSON.stringify(currentAssets);
        
        // Vérifier si la recette a changé (début ou changement de recette)
        let recipeChanged = (this.lastRecipe !== recipeId);
        // Vérifier si les assets ont changé
        let assetsChanged = (this.lastAssets !== assetsId);
        
        // Logic de déclenchement selon les consignes :
        // 1. Recette au début de partie OU quand elle change
        // 2. Assets quand ils changent (mais PAS redéclencher la recette)
        
        if (recipeChanged || (assetsChanged && !recipeChanged)) {
            // Mettre à jour les trackers
            if (recipeChanged) this.lastRecipe = recipeId;
            if (assetsChanged) this.lastAssets = assetsId;
            
            // Construire la nouvelle séquence selon le cas
            let newSequence = [];
            
            if (recipeChanged && currentRecipe && currentRecipe.length > 0) {
                // CAS 1: Recette a changé -> afficher recette PUIS assets
                newSequence.push({
                    type: 'recipe',
                    data: currentRecipe,
                    duration: (this.condition.visual_intention_recipe_duration || 2000)
                });
                
                // Puis ajouter les assets après la recette
                if (currentAssets && currentAssets.length > 0) {
                    currentAssets.forEach(asset => {
                        newSequence.push({
                            type: 'asset',
                            data: asset,
                            duration: (this.condition.visual_intention_asset_duration || 1500)
                        });
                    });
                }
            } else if (assetsChanged && !recipeChanged && currentAssets && currentAssets.length > 0) {
                // CAS 2: Seuls les assets ont changé -> afficher SEULEMENT les nouveaux assets
                currentAssets.forEach(asset => {
                    newSequence.push({
                        type: 'asset',
                        data: asset,
                        duration: (this.condition.visual_intention_asset_duration || 1500)
                    });
                });
            }
            
            // Démarrer la nouvelle séquence
            if (newSequence.length > 0) {
                this._startBubbleSequence(newSequence, sprites, x, y);
            } else {
                this._clearBubbleSequence();
            }
        } else {
            // Aucun changement -> juste mettre à jour la position si une bulle est affichée
            this._updateBubblePosition(x, y);
        }
    }

    /**
     * Start the visual bubble sequence
     */
    _startBubbleSequence(sequence, sprites, x, y) {
        // Vérifications de sécurité
        if (!sequence || sequence.length === 0 || !sprites) {
            return;
        }
        
        // Arrêter la séquence précédente
        this._clearBubbleSequence();

        // Stocker la nouvelle séquence
        this.bubbleSequence = sequence;
        this.currentBubbleIndex = 0;

        // Démarrer l'affichage
        this._showNextBubble(sprites, x, y);
    }

    /**
     * Show the next bubble in sequence
     */
    _showNextBubble(sprites, x, y) {
        if (this.currentBubbleIndex >= this.bubbleSequence.length) {
            this._clearBubbleSequence();
            return;
        }

        let currentBubble = this.bubbleSequence[this.currentBubbleIndex];
        
        // Créer le sprite approprié
        if (currentBubble.type === 'recipe' || currentBubble.type === 'next_recipe') {
            this._createRecipeBubble(currentBubble.data, sprites, x, y);
        } else if (currentBubble.type === 'asset') {
            this._createAssetBubble(currentBubble.data, sprites, x, y);
        }

        // Programmer la bulle suivante
        this.bubbleTimer = setTimeout(() => {
            this.currentBubbleIndex++;
            this._showNextBubble(sprites, x, y);
        }, currentBubble.duration);
    }

    /**
     * Create a recipe bubble sprite
     */
    _createRecipeBubble(recipeData, sprites, x, y) {
        this._clearCurrentBubble();
        
        let spriteFrame = this._ingredientsToSpriteFrame(recipeData, "done");
        this.currentBubbleSprite = this.add.sprite(
            this.tileSize * x + this.tileSize/2,
            this.tileSize * y - 40,
            "soups",
            spriteFrame
        );
        this.currentBubbleSprite.depth = 10;
        this.currentBubbleSprite.setDisplaySize(this.tileSize, this.tileSize);
        this.currentBubbleSprite.setOrigin(0.5);
    }

    /**
     * Create an asset bubble sprite avec fond blanc circulaire pour lisibilité
     */
    _createAssetBubble(assetData, sprites, x, y) {
        this._clearCurrentBubble();
        
        // Mapping vers les bonnes frames et atlas
        const assetToSprite = {
            'O': { atlas: 'objects', frame: 'onion.png' },
            'T': { atlas: 'objects', frame: 'tomato.png' },  
            'D': { atlas: 'objects', frame: 'dish.png' },
            'S': { atlas: 'tiles', frame: 'serve.png' }    // Zone de service depuis tiles (qui charge terrain.json)
        };
        
        let spriteInfo = assetToSprite[assetData];
        if (spriteInfo) {
            // Position de la bulle
            let bubbleX = this.tileSize * x + this.tileSize/2;
            let bubbleY = this.tileSize * y - 40;
            
            // 1. Créer le fond blanc circulaire pour lisibilité
            this.currentBubbleBackground = this.add.graphics();
            this.currentBubbleBackground.fillStyle(0xFFFFFF, 0.9);  // Blanc avec légère transparence
            this.currentBubbleBackground.lineStyle(2, 0x000000, 0.3); // Bordure noire légère
            this.currentBubbleBackground.fillCircle(bubbleX, bubbleY, this.tileSize/4);
            this.currentBubbleBackground.strokeCircle(bubbleX, bubbleY, this.tileSize/4);
            this.currentBubbleBackground.depth = 9; // Derrière le sprite principal
            
            // 2. Créer le sprite de l'asset par-dessus le fond
            this.currentBubbleSprite = this.add.sprite(
                bubbleX,
                bubbleY,
                spriteInfo.atlas,
                spriteInfo.frame
            );
            this.currentBubbleSprite.depth = 10;
            this.currentBubbleSprite.setDisplaySize(this.tileSize * 0.7, this.tileSize * 0.7); // Légèrement plus petit que le fond
            this.currentBubbleSprite.setOrigin(0.5);
        }
    }

    /**
     * Update bubble position when player moves
     */
    _updateBubblePosition(x, y) {
        if (this.currentBubbleSprite) {
            let newX = this.tileSize * x + this.tileSize/2;
            let newY = this.tileSize * y - 40;
            
            // Déplacer le sprite principal
            this.currentBubbleSprite.setPosition(newX, newY);
            
            // Déplacer aussi le fond s'il existe
            if (this.currentBubbleBackground) {
                this.currentBubbleBackground.clear();
                this.currentBubbleBackground.fillStyle(0xFFFFFF, 0.9);
                this.currentBubbleBackground.lineStyle(2, 0x000000, 0.3);
                this.currentBubbleBackground.fillCircle(newX, newY, this.tileSize/4);
                this.currentBubbleBackground.strokeCircle(newX, newY, this.tileSize/4);
            }
        }
    }

    /**
     * Clear current bubble sprite
     */
    _clearCurrentBubble() {
        // Nettoyer le sprite principal
        if (this.currentBubbleSprite) {
            this.currentBubbleSprite.destroy();
            this.currentBubbleSprite = null;
        }
        
        // Nettoyer le fond s'il existe
        if (this.currentBubbleBackground) {
            this.currentBubbleBackground.destroy();
            this.currentBubbleBackground = null;
        }
    }

    /**
     * Clear entire bubble sequence
     */
    _clearBubbleSequence() {
        if (this.bubbleTimer) {
            clearTimeout(this.bubbleTimer);
            this.bubbleTimer = null;
        }
        this._clearCurrentBubble();
        this.currentBubbleIndex = 0;
    }
}