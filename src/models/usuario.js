import { DataTypes } from "sequelize";
import bcrypt from "bcryptjs";

export default (sequelize) => {
    const Usuario = sequelize.define('Usuario', {
        id: {
            type: DataTypes.UUID,
            defaultValue: DataTypes.UUIDV4,
            primaryKey: true,
            allowNull: false,
        },
        nombre: {
            type: DataTypes.STRING(50),
            allowNull: false,
            validate: {
                len: [1, 50],
            },
        },
        correoElectronico: {
            type: DataTypes.STRING(100),
            allowNull: false,
            unique: true,
            validate: {
                isEmail: true,
                len: [5, 100],
            },
        },
        contrasena: {
            type: DataTypes.STRING(255),
            allowNull: false,
            validate: {
                len: [6, 100],
            },
        },
        sueldo: {
            type: DataTypes.FLOAT,
            allowNull: true,
            validate: {
                min: 0,
            },
        },
        porcentajeRSH: {
            type: DataTypes.FLOAT,
            allowNull: true,
            validate: {
                min: 0,
                max: 100,
            },
        },
        profesion: {
            type: DataTypes.STRING(100),
            allowNull: true,
            validate: {
                len: [0, 100],
            },
        },
        fechaNacimiento: {
            type: DataTypes.DATEONLY,
            allowNull: true,
            validate: {
                isDate: true,
            },
        },
        ciudad: {
            type: DataTypes.STRING(100),
            allowNull: true,
            validate: {
                len: [0, 100],
            },
        },
        region: {
            type: DataTypes.STRING(100),
            allowNull: true,
            validate: {
                len: [0, 100],
            },
        },
        firebaseUID: {
            type: DataTypes.STRING(255),
            allowNull: true,
            unique: true,
        },
    }, {
        tableName: 'Usuario',
        timestamps: true,
        hooks: {
            beforeValidate: (usuario) => {
                if (!usuario.codigoUsuario) {
                    usuario.codigoUsuario = Math.floor(Math.random() * (9999 - 1000 + 1)) + 1000;
                }
            },
            beforeCreate: async (usuario) => {
                // Generar codigoUsuario aleatorio si no está proporcionado
                // Hash de la contraseña
                const salt = await bcrypt.genSalt(10);
                usuario.contrasena = await bcrypt.hash(usuario.contrasena, salt);
            },
            beforeUpdate: async (usuario) => {
                // Hash de la contraseña si fue modificada
                if (usuario.changed('contrasena')) {
                    const salt = await bcrypt.genSalt(10);
                    usuario.contrasena = await bcrypt.hash(usuario.contrasena, salt);
                }
            }
        }
    });

    // Método para comparar contraseñas
    Usuario.prototype.compararContrasena = async function(contrasenaIngresada) {
        return await bcrypt.compare(contrasenaIngresada, this.contrasena);
    };

    Usuario.associate = (models) => {
        Usuario.hasMany(models.Mensaje, {
            foreignKey: 'emisorID',
            as: 'mensajesEnviados'
        });
        Usuario.hasMany(models.Chat, {
            foreignKey: 'usuarioID',
            as: 'chats'
        });
    };

    return Usuario;
}