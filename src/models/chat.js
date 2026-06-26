import { DataTypes } from "sequelize";

export default (sequelize) => {
    const Chat = sequelize.define('Chat', {
        id: {
            type: DataTypes.UUID,
            defaultValue: DataTypes.UUIDV4,
            primaryKey: true,
            allowNull: false,
        },
        nombre: {
            type: DataTypes.STRING(100),
            allowNull: false,
            validate: {
                len: [1, 100],
            },
        },
        usuarioID: {
            type: DataTypes.UUID,
            allowNull: false,
            references: {
                model: 'Usuario',
                key: 'id',
            },
        },
    }, {
        tableName: 'Chat',
        timestamps: true,
    });

    Chat.associate = (models) => {
        Chat.belongsTo(models.Usuario, {
            foreignKey: 'usuarioID',
            as: 'usuario',
        });
        Chat.hasMany(models.Mensaje, {
            foreignKey: 'chatID',
            as: 'mensajes',
        });
    };

    return Chat;
};
