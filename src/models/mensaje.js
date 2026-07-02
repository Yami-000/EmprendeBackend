import { DataTypes } from "sequelize";

export default (sequelize) => {
    const Mensaje = sequelize.define('Mensaje', {
        id: {
            type: DataTypes.UUID,
            defaultValue: DataTypes.UUIDV4,
            primaryKey: true,
            allowNull: false,
        },
        chatID: {
            type: DataTypes.UUID,
            allowNull: false,
            references: {
                model: 'Chat',
                key: 'id',
            },
        },
        usuarioID: {
            type: DataTypes.UUID,
            allowNull: true, // Nullable para mensajes generados por IA
            references: {
                model: 'Usuario',
                key: 'id',
            },
        },
        texto: {
            type: DataTypes.STRING(500),
            allowNull: true,
            validate: {
                len: [1, 500],
            },
        },
        archivoAdjuntoURL: {
            type: DataTypes.STRING(255),
            allowNull: true,
            validate: {
                isUrl: true,
                len: [0, 255],
            },
        },
        role: {
            type: DataTypes.ENUM('user', 'assistant'),
            allowNull: false,
            defaultValue: 'user',
        },
        content: {
            type: DataTypes.TEXT,
            allowNull: true,
        },
    }, {
        tableName: 'Mensaje',
        timestamps: true,
    });

    Mensaje.associate = (models) => {
        Mensaje.belongsTo(models.Usuario, {
            foreignKey: 'usuarioID',
            as: 'usuario'
        });
        Mensaje.belongsTo(models.Chat, {
            foreignKey: 'chatID',
            as: 'chat'
        });
    };

    return Mensaje;
}